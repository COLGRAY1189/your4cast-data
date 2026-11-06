"""Encodes layers as 8-bit PNG textures on fixed scales, which the manifest states and the app decodes.

Linear: ``value = min + (max - min) * b / 255``. Sqrt (rain): ``value = max * (b / 255) ** 2``, which keeps light
rain (0.1 mm/h is byte 8) apart from none. Values outside a scale clamp to byte 0 or 255.

Wind is RGB with u in red, v in green and blue 0. It has no alpha channel, because Android premultiplies a PNG's
alpha when it decodes it, which would corrupt the vectors. Scalars are 8-bit grey.
"""

import io
from dataclasses import dataclass
from typing import Literal

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Scale:
    """How one layer's values map to bytes."""

    encoding: Literal["linear", "sqrt"]
    min: float
    max: float
    unit: str


SCALES: dict[str, Scale] = {
    "wind": Scale("linear", -60, 60, "m/s"),
    "temperature": Scale("linear", -70, 60, "°C"),
    "rain": Scale("sqrt", 0, 100, "mm/h"),
    "clouds": Scale("linear", 0, 100, "%"),
}


def to_bytes(values: np.ndarray, scale: Scale) -> np.ndarray:
    """The values as bytes on ``scale``, clamped to its ends."""
    x = np.asarray(values, dtype=np.float64)
    if np.isnan(x).any():
        raise ValueError("a field contains NaN")
    x = np.clip(x, scale.min, scale.max)
    if scale.encoding == "sqrt":
        unit = np.sqrt((x - scale.min) / (scale.max - scale.min))
    else:
        unit = (x - scale.min) / (scale.max - scale.min)
    return np.rint(unit * 255).astype(np.uint8)


def from_bytes(b: np.ndarray, scale: Scale) -> np.ndarray:
    """The values bytes stand for: the app's decode, written here so tests can check the round trip."""
    unit = np.asarray(b, dtype=np.float32) / 255
    if scale.encoding == "sqrt":
        unit = unit * unit
    return (scale.min + unit * (scale.max - scale.min)).astype(np.float32)


def _png(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.save(out, format="PNG", compress_level=9)
    return out.getvalue()


def png_gray(values: np.ndarray, scale: Scale) -> bytes:
    """An 8-bit grey PNG of one scalar layer."""
    return _png(Image.fromarray(to_bytes(values, scale)))  # 2-D uint8 is mode "L"


def png_wind(u: np.ndarray, v: np.ndarray) -> bytes:
    """An RGB PNG of the wind: u in red, v in green, blue 0, no alpha."""
    w = SCALES["wind"]
    r, g = to_bytes(u, w), to_bytes(v, w)
    return _png(Image.fromarray(np.dstack([r, g, np.zeros_like(r)])))  # (h, w, 3) uint8 is mode "RGB"
