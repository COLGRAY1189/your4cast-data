"""Turns ECMWF fields into the map's layers, in the units the app shows."""

import numpy as np

ZERO_C_IN_K = 273.15


def celsius(kelvin: np.ndarray) -> np.ndarray:
    """2 m temperature in °C."""
    return np.asarray(kelvin, dtype=np.float32) - np.float32(ZERO_C_IN_K)


def rain_rate(tp_now: np.ndarray, tp_prev: np.ndarray, hours: int) -> np.ndarray:
    """Mean precipitation rate over the interval, in mm/h.

    ``tp`` is accumulated from the run's start, in metres. Packing noise can make it shrink slightly from one step
    to the next, so the rate is never below zero.
    """
    mm = (np.asarray(tp_now, dtype=np.float32) - np.asarray(tp_prev, dtype=np.float32)) * 1000
    return np.maximum(mm / hours, 0).astype(np.float32)


def cloud_percent(tcc: np.ndarray) -> np.ndarray:
    """Total cloud cover as 0-100 %."""
    return np.clip(np.asarray(tcc, dtype=np.float32) * 100, 0, 100)
