from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import numpy as np
import pandas as pd
import tifffile
from .io import read_localizations, write_exports
from .drift import estimate
from .bridge import morphology


def _sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def render(table, cfg):
    pixel = float(cfg.get("pixel_size_nm", 10))
    if not np.isfinite(pixel) or pixel <= 0:
        raise ValueError("render.pixel_size_nm must be finite and positive")
    xyz = table[["x_nm", "y_nm"]].to_numpy()
    origin = np.floor(xyz.min(axis=0) / pixel) * pixel - pixel
    indices = np.floor((xyz - origin) / pixel).astype(np.int64)
    width, height = (indices.max(axis=0) + 2).tolist()
    if width * height > cfg.get("max_pixels", 100_000_000):
        raise ValueError("Rendered field exceeds max_pixels; check coordinate units/pixel size")
    image = np.zeros((height, width), np.float32)
    np.add.at(image, (indices[:, 1], indices[:, 0]), 1)
    return image, {"pixel_size_nm": pixel, "origin_nm": origin.tolist(),
                   "shape_yx": [height, width], "method": "localization-count histogram",
                   "dimensions": "2D XY projection", "cell_convention": "half-open edges; y increases with row"}


def _localize(cfg, folder):
    inp, settings = cfg["input"], cfg.get("localization", {})
    if settings.get("backend") not in ("picasso", "thunderstorm", "custom"):
        raise ValueError("Movie input requires localization.backend = picasso/thunderstorm/custom")
    command = settings.get("command")
    if command is None:
        from .localize import localize
        backend = settings["backend"]
        output = folder / ("localized.hdf5" if backend == "picasso" else "localized.csv")
        options = {**settings, "input": inp["path"], "output": str(output)}
        localize(options)
        return {**inp, **settings.get("result", {}), "path": str(output),
                "format": "picasso" if backend == "picasso" else "thunderstorm",
                "pixel_size_nm": settings.get("pixel_size_nm", inp.get("pixel_size_nm"))}
    if not isinstance(command, list) or not command or not all(isinstance(s, str) for s in command):
        raise ValueError("localization.command must be an executable argument array")
    output = folder / settings.get("output_filename", "localized.csv")
    if output.parent.resolve() != folder.resolve():
        raise ValueError("output_filename must be a filename inside the results folder")
    args = [s.replace("{input}", str(Path(inp["path"]).resolve())).replace("{output}", str(output.resolve())) for s in command]
    with (folder / "localization.log").open("w", encoding="utf-8") as log:
        subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, check=True,
                       timeout=settings.get("timeout_seconds", 3600))
    if not output.is_file():
        raise FileNotFoundError("Localization command did not produce {output}")
    options = {**inp, **settings.get("result", {}), "path": str(output)}
    return options


def run(config, method=None, output_dir=None):
    """Run from a dict or JSON path. Relative paths resolve beside the JSON file."""
    if isinstance(config, (str, Path)):
        config_path = Path(config).resolve()
        with config_path.open(encoding="utf-8-sig") as f:
            cfg = json.load(f)
        base = config_path.parent
    else:
        cfg = deepcopy(config); base = Path.cwd()
    if method is not None: cfg.setdefault('drift', {})['method'] = method
    if output_dir is not None: cfg['output_dir'] = str(output_dir)
    if cfg.get("schema_version", 1) != 1:
        raise ValueError("Unsupported schema_version")
    for section, key in (("input", "path"), ("drift", "path"), ("morphology", "fiji_dir"), ("localization", "fiji_dir")):
        if cfg.get(section, {}).get(key):
            p = Path(cfg[section][key]); cfg[section][key] = str((base / p).resolve())
    output = Path(cfg.get("output_dir", "results/run"))
    output = (base / output).resolve()
    # One run, one fresh directory: no stale morphology tables after failures.
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": 1, "morstorm_version": "0.6.0rc1", "language": "python", "variant": "B", "matlab_required": False,
                "started_utc": datetime.now(timezone.utc).isoformat(), "status": "running",
                "config": cfg, "python": platform.python_version(), "packages": {}}
    for pkg in ("numpy", "scipy", "pandas", "numba", "tifffile", "h5py", "picassosr"):
        try: manifest["packages"][pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError: pass
    def save_manifest():
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    save_manifest()
    try:
        inp = cfg["input"]
        manifest["input_sha256"] = _sha256(inp["path"])
        kind = inp.get("kind", "localizations")
        if kind not in ("localizations", "movie"):
            raise ValueError("input.kind must be localizations or movie")
        if kind == "movie": inp = _localize(cfg, output)
        locs = read_localizations(inp["path"], inp)
        drift_cfg = {"pixel_size_nm": locs.metadata.get("pixel_size_nm"), **cfg.get("drift", {})}
        curve, diagnostics = estimate(locs.table, drift_cfg)
        locs.table[locs.axes] = locs.table[locs.axes].to_numpy() - curve[locs.table.frame.to_numpy() - 1]
        write_exports(locs, output)
        pd.DataFrame(np.column_stack([np.arange(1, len(curve) + 1), curve]),
                     columns=["frame"] + ["d" + a for a in locs.axes]).to_csv(output / "drift.csv", index=False, float_format="%.12g")
        image, rendering = render(locs.table, cfg.get("render", {}))
        tifffile.imwrite(output / "density.tif", image, photometric="minisblack", metadata=None)
        locs.table[["x_nm", "y_nm"]].to_csv(output / "coordinates.csv", index=False, float_format="%.17g")
        (output / "render.json").write_text(json.dumps(rendering, indent=2), encoding="utf-8")
        manifest.update({"localizations": len(locs.table), "input_metadata": locs.metadata,
                         "drift": diagnostics, "render": rendering})
        morph_cfg = cfg.get("morphology", {})
        if morph_cfg.get("enabled", True):
            manifest["morphology"] = morphology(output, rendering, morph_cfg)
            manifest["status"] = "complete"
        else:
            manifest["status"] = "preprocessing_only"
        manifest["output_sha256"] = {p.name: _sha256(p) for p in output.iterdir() if p.suffix in (".csv", ".tif")}
    except Exception as e:
        manifest["status"] = "failed"; manifest["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat(); save_manifest()
    return manifest
