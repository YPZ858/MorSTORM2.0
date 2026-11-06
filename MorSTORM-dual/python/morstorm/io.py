"""Explicit unit conversion; input row order and non-coordinate fields are retained."""
from dataclasses import dataclass, field
from pathlib import Path
import re
import h5py
import numpy as np
import pandas as pd
import yaml


@dataclass
class Localizations:
    table: pd.DataFrame
    metadata: dict = field(default_factory=dict)
    original_records: object = None
    picasso_info: list = field(default_factory=list)

    @property
    def axes(self):
        return [c for c in ("x_nm", "y_nm", "z_nm") if c in self.table]

    def validate(self):
        t = self.table
        if t.empty or not {"frame", "x_nm", "y_nm"}.issubset(t):
            raise ValueError("Nonempty localizations with frame, x_nm, y_nm required")
        a = t[["frame"] + self.axes].to_numpy(dtype=float)
        if not np.isfinite(a).all():
            raise ValueError("Nonfinite frame/coordinates; filter explicitly before analysis")
        f = a[:, 0]
        if (f < 1).any() or (f != np.floor(f)).any():
            raise ValueError("Canonical frames must be positive integers")
        t["frame"] = f.astype(np.int64)
        return self


def _positive_pixel(value):
    if value is None or not np.isfinite(value) or value <= 0:
        raise ValueError("pixel_size_nm must be explicitly supplied for pixel coordinates")
    return float(value)


def read_localizations(path, cfg):
    path = Path(path)
    fmt = cfg.get("format", "auto")
    if fmt == "auto":
        fmt = "picasso" if path.suffix.lower() in (".hdf5", ".h5") else "csv"
    if fmt == "picasso":
        with h5py.File(path, "r") as h:
            records = h["locs"][:]
        if not records.dtype.names or not {"frame", "x", "y"}.issubset(records.dtype.names):
            raise ValueError("Picasso /locs must be a compound dataset with frame, x, y")
        info = []
        sidecar = path.with_suffix(".yaml")
        if sidecar.exists():
            with sidecar.open(encoding="utf-8") as f:
                info = [v for v in yaml.safe_load_all(f) if isinstance(v, dict)]
        pixel = cfg.get("pixel_size_nm")
        if pixel is None:
            pixel = next((d["Pixelsize"] for d in reversed(info) if "Pixelsize" in d), None)
        pixel = _positive_pixel(pixel)
        t = pd.DataFrame.from_records(records)
        t["frame"] = t["frame"].astype(np.int64) + 1
        for axis in ("x", "y", "z"):
            if axis in t:
                # Picasso x/y are camera pixels; z is already nm.
                t[axis + "_nm"] = t.pop(axis).astype(float) * (1 if axis == "z" else pixel)
        cols = ["frame", "x_nm", "y_nm"] + (["z_nm"] if "z_nm" in t else [])
        t = t[cols + [c for c in t if c not in cols]]
        locs = Localizations(t, {"source": str(path), "format": fmt,
                             "pixel_size_nm": pixel}, records, info).validate()
        return _offset(locs, cfg)
    if fmt not in ("csv", "thunderstorm"):
        raise ValueError("format must be auto, csv, thunderstorm or picasso")
    t = pd.read_csv(path)
    t.columns = [str(c).strip() for c in t.columns]
    mapping = cfg.get("columns", {})
    normalized = {re.sub(r"[^a-z0-9]", "", c.lower()): c for c in t}
    renamed = {}
    for target, aliases in {"frame": ("frame",), "x_nm": ("xnm",),
                            "y_nm": ("ynm",), "z_nm": ("znm",)}.items():
        source = mapping.get(target)
        if source is None:
            source = next((normalized[a] for a in aliases if a in normalized), None)
        if source is not None:
            if source not in t:
                raise ValueError(f"Column {source!r} does not exist")
            renamed[source] = target
    t = t.rename(columns=renamed)
    if t.columns.duplicated().any():
        raise ValueError("Duplicate canonical columns after mapping")
    # Bare x/y are ambiguous: only accept an explicit mapping and coordinate_unit.
    if not {"frame", "x_nm", "y_nm"}.issubset(t):
        raise ValueError("Ambiguous CSV: map columns to frame/x_nm/y_nm; specify coordinate_unit")
    unit = cfg.get("coordinate_unit", "nm")
    if unit not in ("nm", "pixel"):
        raise ValueError("coordinate_unit must be nm or pixel")
    if unit == "pixel":
        pixel = _positive_pixel(cfg.get("pixel_size_nm"))
        t[[c for c in ("x_nm", "y_nm", "z_nm") if c in t]] *= pixel
    base = cfg.get("frame_base", 1)
    if base not in (0, 1):
        raise ValueError("frame_base must be 0 or 1")
    t["frame"] = pd.to_numeric(t["frame"]) + (1 - base)
    cols = ["frame", "x_nm", "y_nm"] + (["z_nm"] if "z_nm" in t else [])
    t = t[cols + [c for c in t if c not in cols]]
    return _offset(Localizations(t, {"source": str(path), "format": fmt,
                         "pixel_size_nm": cfg.get("pixel_size_nm")}).validate(), cfg)


def _offset(locs, cfg):
    offset = np.asarray(cfg.get("coordinate_offset_nm", [0] * len(locs.axes)), dtype=float)
    if offset.shape != (len(locs.axes),) or not np.isfinite(offset).all():
        raise ValueError("coordinate_offset_nm must contain one finite value per spatial axis")
    locs.table[locs.axes] = locs.table[locs.axes].to_numpy() + offset
    locs.metadata["coordinate_offset_nm"] = offset.tolist()
    return locs


def write_exports(locs, folder):
    folder = Path(folder)
    locs.table.to_csv(folder / "corrected.csv", index=False, float_format="%.12g")
    cols = ["frame"] + locs.axes
    thunder = locs.table[cols].rename(columns={a: a[0] + " [nm]" for a in locs.axes})
    thunder.to_csv(folder / "thunderstorm.csv", index=False, float_format="%.12g")
    if locs.original_records is not None:
        records = locs.original_records.copy()
        pixel = locs.metadata["pixel_size_nm"]
        for axis in ("x", "y", "z"):
            if axis in records.dtype.names:
                records[axis] = locs.table[axis + "_nm"].to_numpy() / (1 if axis == "z" else pixel)
        with h5py.File(folder / "picasso_corrected.hdf5", "w") as h:
            h.create_dataset("locs", data=records)
        info = locs.picasso_info + [{"Generated by": "MorSTORM 0.5.0rc1",
                                    "Pixelsize": pixel, "Coordinates": "x/y pixel, z nm"}]
        with (folder / "picasso_corrected.yaml").open("w", encoding="utf-8") as f:
            yaml.safe_dump_all(info, f, sort_keys=False)
