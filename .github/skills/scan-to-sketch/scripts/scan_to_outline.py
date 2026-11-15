# /// script
# requires-python = ">=3.11"
# dependencies = ["opencv-python-headless>=4.8", "numpy>=1.26", "pillow>=10.0", "ezdxf>=1.1"]
# ///
"""Flatbed scan / orthographic photo -> calibrated outline (DXF + SVG + JSON manifest + overlay).

Usage:
    uv run scan_to_outline.py scan.png --calib 548,228,548,864,80.75 [--calib ...] [-o out/]
    uv run scan_to_outline.py scan.png --dpi 600            # NOMINAL scale only (flagged)

Calibration (strongest first):
  --calib x1,y1,x2,y2,mm   two pixel points spanning a caliper-measured distance. One gives an
                           isotropic scale; one roughly along X plus one roughly along Y gives
                           separate X/Y scales (flatbed sensor and transport axes differ).
  --dpi N / image metadata NOMINAL scale; flagged in the manifest, never treat it as measured.

Extraction: grayscale -> CLAHE -> blur -> Otsu threshold (part darker than background, else
--invert) -> contours with holes -> drop contours shorter than --min-length-mm -> simplify to
--tolerance-mm. Near-circular contours are fitted as circles (centre, diameter, RMS residual).
Output coordinates: mm, X right, Y up, origin at the outer contour's bounding-box centre
(--mirror flips X for parts scanned face-down through the glass).

Exit codes: 0 OK, 1 no contour found, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import cv2
import ezdxf
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Calibration:
    p1: tuple[float, float]
    p2: tuple[float, float]
    mm: float

    @property
    def px(self) -> float:
        return math.dist(self.p1, self.p2)

    @property
    def axis(self) -> str:
        return "x" if abs(self.p2[0] - self.p1[0]) >= abs(self.p2[1] - self.p1[1]) else "y"

    @classmethod
    def parse(cls, text: str) -> Calibration:
        x1, y1, x2, y2, mm = (float(v) for v in text.split(","))
        if mm <= 0 or (x1, y1) == (x2, y2):
            raise ValueError(f"degenerate calibration {text!r}")
        return cls((x1, y1), (x2, y2), mm)


@dataclass(frozen=True)
class Scale:
    mm_per_px_x: float
    mm_per_px_y: float
    state: str  # calibrated | calibrated_per_axis | nominal
    source: Any


@dataclass
class Shape:
    kind: str  # circle | polyline
    hole: bool
    bbox_mm: list[float]
    points_mm: list[list[float]]
    circle: dict[str, Any] | None = field(default=None)


def resolve_scale(calibrations: list[Calibration], dpi: float | None, image: Path) -> Scale | None:
    if calibrations:
        per_axis = {c.axis: c.mm / c.px for c in calibrations}
        if len(per_axis) == 2:
            return Scale(
                per_axis["x"], per_axis["y"], "calibrated_per_axis", [asdict(c) for c in calibrations]
            )
        s = sum(c.mm for c in calibrations) / sum(c.px for c in calibrations)
        return Scale(s, s, "calibrated", [asdict(c) for c in calibrations])
    if dpi is None:
        meta = Image.open(image).info.get("dpi")
        dpi = float(meta[0]) if meta and meta[0] > 1 else None
    if dpi is None:
        return None
    return Scale(25.4 / dpi, 25.4 / dpi, "nominal", {"dpi": dpi})


def fit_circle(pts: np.ndarray) -> tuple[float, float, float, float]:
    """Algebraic least-squares circle: centre x, centre y, radius, RMS radial residual."""
    x, y = pts[:, 0], pts[:, 1]
    a = np.column_stack([x, y, np.ones_like(x)])
    cx2, cy2, c = np.linalg.lstsq(a, x * x + y * y, rcond=None)[0]
    cx, cy = cx2 / 2, cy2 / 2
    r = math.sqrt(c + cx * cx + cy * cy)
    rms = float(np.sqrt(np.mean((np.hypot(x - cx, y - cy) - r) ** 2)))
    return float(cx), float(cy), r, rms


def extract_contours(
    gray: np.ndarray, invert: bool, mm_per_px: float, min_len_mm: float
) -> list[tuple[np.ndarray, bool]]:
    """(pixel contour, is_hole) for every contour longer than min_len_mm."""
    g = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    g = cv2.GaussianBlur(g, (5, 5), 0)
    mode = cv2.THRESH_BINARY if invert else cv2.THRESH_BINARY_INV
    _, mask = cv2.threshold(g, 0, 255, mode + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hierarchy is None:
        return []
    return [
        (c[:, 0, :].astype(float), bool(h[3] >= 0))
        for c, h in zip(contours, hierarchy[0], strict=True)
        if cv2.arcLength(c, True) * mm_per_px >= min_len_mm
    ]


def to_shapes(
    found: list[tuple[np.ndarray, bool]],
    scale: Scale,
    mirror: bool,
    tolerance_mm: float,
    circle_rms_mm: float,
) -> list[Shape]:
    outers = [c for c, hole in found if not hole] or [found[0][0]]
    outer = max(outers, key=lambda c: cv2.contourArea(c.astype(np.float32)))
    ox, oy = (outer.min(0) + outer.max(0)) / 2
    flip = -1 if mirror else 1

    def to_mm(p: np.ndarray) -> np.ndarray:
        return np.column_stack(
            [flip * (p[:, 0] - ox) * scale.mm_per_px_x, -(p[:, 1] - oy) * scale.mm_per_px_y]
        )

    eps_px = tolerance_mm / min(scale.mm_per_px_x, scale.mm_per_px_y)
    shapes = []
    for contour, hole in found:
        mm = to_mm(contour)
        cx, cy, r, rms = fit_circle(mm)
        simple = to_mm(cv2.approxPolyDP(contour.astype(np.float32).reshape(-1, 1, 2), eps_px, True)[:, 0, :])
        is_circle = rms <= circle_rms_mm and r > 0
        shapes.append(
            Shape(
                kind="circle" if is_circle else "polyline",
                hole=hole,
                bbox_mm=[round(float(v), 3) for v in (*mm.min(0), *mm.max(0))],
                points_mm=[[round(float(x), 3), round(float(y), 3)] for x, y in simple],
                circle={"center": [round(cx, 3), round(cy, 3)], "d": round(2 * r, 3), "rms": round(rms, 4)}
                if is_circle
                else None,
            )
        )
    return shapes


def write_dxf(shapes: list[Shape], path: Path) -> None:
    doc = ezdxf.new("R2000", setup=False)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    for s in shapes:
        layer = {"layer": "HOLES" if s.hole else "OUTLINE"}
        if s.circle is not None:
            msp.add_circle(s.circle["center"], s.circle["d"] / 2, dxfattribs=layer)
        else:
            msp.add_lwpolyline(s.points_mm, close=True, dxfattribs=layer)
    doc.saveas(path)


def write_svg(shapes: list[Shape], path: Path) -> None:
    pts = np.vstack([np.array(s.points_mm) for s in shapes])
    lo, hi = pts.min(0) - 2, pts.max(0) + 2
    elems = []
    for s in shapes:
        if s.circle is not None:
            (x, y), r = s.circle["center"], s.circle["d"] / 2
            elems.append(f'<circle cx="{x}" cy="{-y}" r="{r}"/>')
        else:
            elems.append('<polygon points="' + " ".join(f"{x},{-y}" for x, y in s.points_mm) + '"/>')
    w, h = hi - lo
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.2f}mm" height="{h:.2f}mm" '
        f'viewBox="{lo[0]:.3f} {-hi[1]:.3f} {w:.3f} {h:.3f}">'
        f'<g fill="none" stroke="black" stroke-width="0.1">{"".join(elems)}</g></svg>\n',
        encoding="utf-8",
    )


def build_manifest(image: Path, scale: Scale, mirror: bool, shapes: list[Shape]) -> dict[str, Any]:
    outer = [s for s in shapes if not s.hole] or shapes
    b = np.array([s.bbox_mm for s in outer])
    extent = [round(float(b[:, 2].max() - b[:, 0].min()), 3), round(float(b[:, 3].max() - b[:, 1].min()), 3)]
    return {
        "source_image": image.name,
        "scale_state": scale.state,
        "scale_source": scale.source,
        "mm_per_px": [scale.mm_per_px_x, scale.mm_per_px_y],
        "edge_uncertainty_mm": round(2 * max(scale.mm_per_px_x, scale.mm_per_px_y), 4),
        "mirrored": mirror,
        "outer_extent_mm": extent,
        "warnings": ["NOMINAL scale from dpi: calibrate against a caliper dimension before modelling"]
        if scale.state == "nominal"
        else [],
        "shapes": [asdict(s) for s in shapes],
    }


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--calib", action="append", default=[], help="x1,y1,x2,y2,mm (repeatable)")
    ap.add_argument("--dpi", type=float)
    ap.add_argument("--invert", action="store_true", help="part is lighter than the background")
    ap.add_argument("--mirror", action="store_true", help="flip X (part scanned face-down)")
    ap.add_argument("--min-length-mm", type=float, default=1.0)
    ap.add_argument("--tolerance-mm", type=float, default=0.05)
    ap.add_argument("--circle-rms-mm", type=float, default=0.05, help="max residual to report a circle")
    ap.add_argument("-o", "--out", default=".")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    image = Path(args.image)
    try:
        gray = cv2.imread(str(image), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            raise ValueError(f"cannot read image {image}")
        scale = resolve_scale([Calibration.parse(c) for c in args.calib], args.dpi, image)
        if scale is None:
            raise ValueError("no scale: pass --calib (preferred) or --dpi")
    except Exception as err:
        print(f"usage error: {err}", file=sys.stderr)
        return 2

    found = extract_contours(gray, args.invert, min(scale.mm_per_px_x, scale.mm_per_px_y), args.min_length_mm)
    if not found:
        print("FAILED: no contour found (try --invert or check contrast)", file=sys.stderr)
        return 1
    shapes = to_shapes(found, scale, args.mirror, args.tolerance_mm, args.circle_rms_mm)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_dxf(shapes, out / f"{image.stem}_outline.dxf")
    write_svg(shapes, out / f"{image.stem}_outline.svg")
    overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    cv2.drawContours(overlay, [c.astype(np.int32).reshape(-1, 1, 2) for c, _ in found], -1, (0, 0, 255), 1)
    cv2.imwrite(str(out / f"{image.stem}_overlay.png"), overlay)
    manifest = build_manifest(image, scale, args.mirror, shapes)
    (out / f"{image.stem}_outline.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")

    n_circles = sum(s.kind == "circle" for s in shapes)
    print(
        f"{scale.state} scale {scale.mm_per_px_x:.6f}/{scale.mm_per_px_y:.6f} mm/px; outer "
        f"{manifest['outer_extent_mm']} mm; {len(shapes)} contours ({n_circles} circles) -> {out}"
    )
    for warning in manifest["warnings"]:
        print("WARNING:", warning)
    return 0


if __name__ == "__main__":
    sys.exit(main())
