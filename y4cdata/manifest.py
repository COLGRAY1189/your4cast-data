"""Which file each map frame uses, and the manifest the app reads. The contract is in docs/manifest.md."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from y4cdata.encode import SCALES
from y4cdata.extended import extended_block
from y4cdata.grib import HEIGHT, WIDTH
from y4cdata.runs import Run

LAYERS = ("wind", "temperature", "rain", "clouds")
SOURCE = "Contains modified ECMWF open data (CC BY 4.0), changed by Your4cast. IFS 0.25°, stream oper."
VERSION = 1


@dataclass(frozen=True)
class Frame:
    """One moment on the map, and the (run, step) each layer is drawn from."""

    time: datetime
    sources: dict[str, tuple[Run, int]] = field(default_factory=dict)


def file_name(run: Run, layer: str, step: int) -> str:
    return f"frames/{run.key}/{layer}-{step:03d}.png"


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def frame_plan(full: Run, short: Run | None) -> list[Frame]:
    """A frame for each of the full run's map steps. Each layer comes from the newest run that has that moment;
    rain needs an interval, so a run's step 0 never supplies it."""
    newest_first = [r for r in (short, full) if r is not None]
    frames = []
    for full_step in full.map_steps():
        t = full.time + timedelta(hours=full_step)
        sources: dict[str, tuple[Run, int]] = {}
        for layer in LAYERS:
            for run in newest_first:
                step = int((t - run.time) / timedelta(hours=1))
                if step in run.map_steps() and not (layer == "rain" and step == 0):
                    sources[layer] = (run, step)
                    break
        frames.append(Frame(t, sources))
    return frames


def build_manifest(frames: list[Frame], full: Run, short: Run | None, generated: datetime) -> dict:
    layers = {}
    for name in LAYERS:
        s = SCALES[name]
        layers[name] = {"encoding": s.encoding, "min": s.min, "max": s.max, "unit": s.unit}
    layers["wind"]["channels"] = ["u", "v"]
    return {
        "version": VERSION,
        "generated": _iso(generated),
        "runs": [_iso(r.time) for r in (full, short) if r is not None],
        "source": SOURCE,
        "grid": {"width": WIDTH, "height": HEIGHT, "lon0": -180.0, "lat0": 90.0, "dlon": 0.25, "dlat": -0.25},
        "layers": layers,
        "frames": [
            {"time": _iso(f.time)} | {layer: file_name(run, layer, step) for layer, (run, step) in f.sources.items()}
            for f in frames
        ],
        "extended": extended_block(full),
    }
