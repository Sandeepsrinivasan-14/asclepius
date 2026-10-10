"""Imaging workstation backend: synthetic phantoms, a classical atlas-subtraction detector and heat-map overlays.

The images are procedurally generated phantoms, not patient scans. The detector is a transparent
atlas-subtraction method used to demonstrate the viewer, overlay and verification workflow. A real model
(for example a Grad-CAM-enabled network) plugs in by replacing `detect`.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image

SIZE = 256


@dataclass(frozen=True)
class Study:
    id: str
    title: str
    modality: str
    body_part: str
    slices: int
    lesion: tuple[float, float, float, float] | None  # cx, cy, radius_px at centre slice, contrast
    seed: int
    note: str


STUDIES: dict[str, Study] = {
    "MR-BRAIN-A": Study("MR-BRAIN-A", "Brain MRI, axial T1 (phantom A)", "MR", "BRAIN", 24, (150, 108, 17, 0.55), 11, "Synthetic phantom with a focal bright lesion in the right frontal region."),
    "MR-BRAIN-B": Study("MR-BRAIN-B", "Brain MRI, axial T1 (phantom B)", "MR", "BRAIN", 24, None, 12, "Synthetic phantom without a lesion (negative control)."),
    "CR-CHEST-A": Study("CR-CHEST-A", "Chest radiograph, PA (phantom)", "CR", "CHEST", 1, (84, 168, 24, 0.42), 13, "Synthetic phantom with a right lower zone opacity."),
}


def _smooth_noise(rng: np.random.Generator, sigma: float, amp: float) -> np.ndarray:
    n = rng.normal(size=(SIZE, SIZE))
    f = np.fft.fft2(n)
    ky, kx = np.meshgrid(np.fft.fftfreq(SIZE), np.fft.fftfreq(SIZE), indexing="ij")
    f *= np.exp(-(kx ** 2 + ky ** 2) * (sigma ** 2) * 2 * np.pi ** 2)
    out = np.real(np.fft.ifft2(f))
    return out / (out.std() + 1e-9) * amp


def _grid() -> tuple[np.ndarray, np.ndarray]:
    return np.meshgrid(np.arange(SIZE), np.arange(SIZE))


def _blob(cx: float, cy: float, r: float) -> np.ndarray:
    x, y = _grid()
    return np.exp(-(((x - cx) ** 2 + (y - cy) ** 2) / (2 * (r / 1.6) ** 2)))


def lesion_scale(study: Study, i: int) -> float:
    """Lesion radius multiplier across slices (zero outside the lesion's extent)."""
    if study.lesion is None:
        return 0.0
    if study.slices == 1:
        return 1.0
    c = study.slices * 0.5
    half = study.slices * 0.28
    d = abs(i - c) / half
    return float(np.sqrt(max(1 - d * d, 0.0)))


def render(study: Study, i: int, *, with_lesion: bool = True, seed_offset: int = 0) -> np.ndarray:
    """Return a float image in [0, 1] for slice i."""
    if not 0 <= i < study.slices:
        raise IndexError("slice out of range")
    rng = np.random.default_rng(study.seed * 1000 + i + seed_offset)
    x, y = _grid()
    if study.body_part == "BRAIN":
        t = (i - study.slices / 2) / (study.slices / 2)
        a, b = 92 * (1 - 0.35 * t * t) ** .5, 108 * (1 - 0.3 * t * t) ** .5
        r2 = ((x - SIZE / 2) / a) ** 2 + ((y - SIZE / 2) / b) ** 2
        skull = ((r2 < 1.18) & (r2 > .96)).astype(float) * .95
        brain = (r2 <= .96).astype(float) * (0.50 + _smooth_noise(rng, 3.0, 0.035))
        vent = np.zeros_like(brain)
        for sx in (-1, 1):
            v = (((x - SIZE / 2 - sx * 17) / 11) ** 2 + ((y - SIZE / 2 + 6) / (30 * (1 - .4 * abs(t)))) ** 2) < 1
            vent += v.astype(float)
        img = skull + brain * (1 - np.clip(vent, 0, 1) * .8)
        img += _smooth_noise(rng, 1.0, 0.012) * (r2 <= 1.0)
    else:  # chest
        lung_l = (((x - 92) / 46) ** 2 + ((y - 128) / 82) ** 2) < 1
        lung_r = (((x - 164) / 46) ** 2 + ((y - 128) / 82) ** 2) < 1
        body = (((x - 128) / 112) ** 2 + ((y - 128) / 122) ** 2) < 1
        img = body * 0.58
        img = np.where(lung_l | lung_r, 0.22 + _smooth_noise(rng, 6, .02), img)
        heart = (((x - 118) / 30) ** 2 + ((y - 150) / 40) ** 2) < 1
        img = np.where(heart, 0.62, img)
        for k in range(7):
            yy = 50 + k * 22
            rib = np.abs(y - (yy + 0.0025 * (x - 128) ** 2 * (1 if k % 2 else .7))) < 2.2
            img = img + rib * body * 0.07 * (1 + _smooth_noise(rng, 5, .15))
        img += (np.abs(x - 128) < 6) * body * .1
    if with_lesion and study.lesion is not None:
        cx, cy, r, contrast = study.lesion
        s = lesion_scale(study, i)
        if s > 0.05:
            img = img + contrast * s * _blob(cx, cy, r * s)
    img += rng.normal(0, 0.012, img.shape)
    return np.clip(img, 0, 1)


def roi_mask(study: Study, i: int) -> np.ndarray:
    x, y = _grid()
    if study.body_part == "BRAIN":
        t = (i - study.slices / 2) / (study.slices / 2)
        a, b = 92 * (1 - 0.35 * t * t) ** .5, 108 * (1 - 0.3 * t * t) ** .5
        return ((((x - SIZE / 2) / a) ** 2 + ((y - SIZE / 2) / b) ** 2) < 0.80).astype(float)
    lung_l = (((x - 92) / 46) ** 2 + ((y - 128) / 82) ** 2) < 0.8
    lung_r = (((x - 164) / 46) ** 2 + ((y - 128) / 82) ** 2) < 0.8
    return (lung_l | lung_r).astype(float)


def detect(img: np.ndarray, atlas: np.ndarray, mask: np.ndarray, sigma: float = 5.0) -> dict[str, Any]:
    """Atlas-subtraction detector: smooth the positive deviation from a normal-anatomy template inside a region of interest."""
    diff = np.clip(img - atlas, 0, None) * mask
    k = _gauss_kernel(sigma)
    resp = np.real(np.fft.ifft2(np.fft.fft2(diff) * np.fft.fft2(k))) * mask
    peak = float(resp.max())
    yy, xx = np.unravel_index(int(resp.argmax()), resp.shape)
    heat = np.clip(resp / max(peak, 1e-9), 0, 1) if peak > 0 else resp
    return {"heat": heat, "peak": peak, "x": int(xx), "y": int(yy)}


def _gauss_kernel(sigma: float) -> np.ndarray:
    x = np.arange(SIZE) - SIZE // 2
    xx, yy = np.meshgrid(x, x)
    g = np.exp(-(xx ** 2 + yy ** 2) / (2 * sigma ** 2))
    g = np.fft.ifftshift(g)
    return g / g.sum()


THRESH = 0.15


def score(peak: float) -> float:
    return float(1 / (1 + np.exp(-(peak - THRESH) * 40)))


def atlas(study: Study, i: int) -> np.ndarray:
    """Normal-anatomy template for the same slice (no lesion, independent noise)."""
    return render(study, i, with_lesion=False, seed_offset=7919)


def analyse(study: Study) -> dict[str, Any]:
    per_slice = []
    best = None
    for i in range(study.slices):
        d = detect(render(study, i), atlas(study, i), roi_mask(study, i))
        per_slice.append(round(score(d["peak"]), 3))
        if best is None or d["peak"] > best[1]["peak"]:
            best = (i, d)
    assert best is not None
    i, d = best
    prob = score(d["peak"])
    return {"study": study.id, "finding": "possible focal lesion" if prob >= 0.5 else "no focal lesion detected", "probability": round(prob, 3), "best_slice": i, "location": {"x": d["x"], "y": d["y"]},
            "per_slice_probability": per_slice, "detector": "atlas subtraction (deviation from a normal-anatomy template, Gaussian-smoothed)",
            "disclaimer": "Demonstration on a synthetic phantom with a classical detector. Not a diagnostic device. Plug in a validated model to use real scans."}


def to_png(img: np.ndarray, window: tuple[float, float] | None = None) -> bytes:
    lo, hi = window or (0.0, 1.0)
    arr = np.clip((img - lo) / max(hi - lo, 1e-6), 0, 1)
    buf = io.BytesIO()
    Image.fromarray((arr * 255).astype(np.uint8), "L").save(buf, "PNG")
    return buf.getvalue()


def overlay_png(heat: np.ndarray, threshold: float = 0.25) -> bytes:
    h = np.clip((heat - threshold) / (1 - threshold), 0, 1)
    r = np.clip(1.5 - np.abs(4 * h - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * h - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * h - 1), 0, 1)
    a = (h ** 0.7) * 0.85
    rgba = np.dstack([r, g, b, a])
    buf = io.BytesIO()
    Image.fromarray((rgba * 255).astype(np.uint8), "RGBA").save(buf, "PNG")
    return buf.getvalue()


def metadata(study: Study) -> dict[str, Any]:
    return {"PatientName": "SYNTHETIC^PHANTOM", "PatientID": f"PH-{study.id}", "Modality": study.modality, "BodyPartExamined": study.body_part, "StudyDescription": study.title,
            "Rows": SIZE, "Columns": SIZE, "NumberOfFrames": study.slices, "PixelSpacing": [0.9, 0.9], "SliceThickness": 5.0 if study.slices > 1 else None,
            "WindowCenter": 0.5, "WindowWidth": 1.0, "BitsAllocated": 8, "Synthetic": True}
