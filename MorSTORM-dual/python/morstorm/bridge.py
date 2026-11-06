"""Both language versions call the same headless Java/MorphoLibJ code."""
from pathlib import Path
import base64
import os
import re
import subprocess


def resource(name):
    bundled = Path(__file__).parent / "resources" / name
    return bundled if bundled.exists() else Path(__file__).resolve().parents[2] / "shared" / name


def _version(path):
    return tuple(int(n) for n in re.findall(r"\d+", path.name))


def morphology(folder, rendering, config):
    folder = Path(folder)
    fiji = Path(config["fiji_dir"])
    ij = sorted((fiji / "jars").glob("ij-*.jar"), key=_version)
    morph = sorted(fiji.rglob("MorphoLibJ_*.jar"), key=_version)
    jar = resource("morstorm-morphology.jar")
    if not ij or not morph or not jar.is_file():
        raise FileNotFoundError("Need Fiji jars/ij-*.jar, MorphoLibJ_*.jar and built shared/morstorm-morphology.jar")
    cp = os.pathsep.join(str(p.resolve()) for p in (jar, ij[-1], morph[-1]))
    java = config.get("java_executable")
    if not java:
        candidates = list((fiji / "java").glob("**/bin/java.exe")) + list((fiji / "java").glob("**/bin/java"))
        java = str(candidates[-1]) if candidates else "java"
    data = [str((folder / "density.tif").resolve()), str(folder.resolve()),
            str(rendering["pixel_size_nm"]), *map(str, rendering["origin_nm"]),
            str(config.get("sigma_px", 1.0)), str(config.get("threshold", 0.2)),
            str(config.get("connectivity", 8)), str(config.get("min_area_nm2", 0)),
            str(config.get("exclude_border", False)).lower(), str((folder / "coordinates.csv").resolve())]
    # Legacy Windows Java launchers lose non-ANSI path arguments. ASCII transport
    # with UTF-8 decoding inside the JVM preserves Unicode output/data paths.
    args = [java, "-Djava.awt.headless=true", "-Dfile.encoding=UTF-8", "-cp", cp,
            "MorstormMorphology", "--base64"] + [base64.b64encode(s.encode("utf-8")).decode("ascii") for s in data]
    with (folder / "morpholibj.log").open("w", encoding="utf-8") as log:
        completed = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT,
                                   timeout=config.get("timeout_seconds", 600), check=False)
    if completed.returncode:
        raise RuntimeError(f"MorphoLibJ exited {completed.returncode}; see {folder / 'morpholibj.log'}")
    return {"engine": "MorphoLibJ", "jar": str(morph[-1]), "imagej_jar": str(ij[-1]),
            "bridge": str(jar), "dimensions": "2D XY projection"}
