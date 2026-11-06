"""Rebuild the small shared Java bridge against a user-installed Fiji.

python scripts/build_bridge.py --fiji C:/path/Fiji.app --javac C:/path/javac.exe
"""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED
import os

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--fiji", type=Path, required=True)
parser.add_argument("--javac", default="javac", help="JDK >=9 javac; emits Java 8 bytecode")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
versions = lambda p: (tuple(int(n) for n in re.findall(r"\d+", p.name)), p.name)
ij = sorted((args.fiji / "jars").glob("ij-*.jar"), key=versions)[-1]
morph = sorted(args.fiji.rglob("MorphoLibJ_*.jar"), key=versions)[-1]
build = root / "build"; build.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=build) as temp:
    subprocess.run([args.javac, "--release", "8", "-cp", os.pathsep.join(map(str, (ij, morph))),
                    "-d", temp, str(root / "shared/MorstormMorphology.java"), str(root / "shared/MorstormThunderstorm.java")], check=True)
    with ZipFile(root / "shared/morstorm-morphology.jar", "w", ZIP_DEFLATED) as z:
        z.write(Path(temp) / "MorstormMorphology.class", "MorstormMorphology.class")
        z.write(Path(temp) / "MorstormThunderstorm.class", "MorstormThunderstorm.class")
print(root / "shared/morstorm-morphology.jar")
