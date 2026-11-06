"""Bundle the shared bridge in wheels; editable installs use repository shared/."""
from pathlib import Path
from shutil import copy2
from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        source = Path(__file__).parent / "shared" / "morstorm-morphology.jar"
        if not source.is_file():
            raise RuntimeError("Build shared/morstorm-morphology.jar before packaging")
        target = Path(self.build_lib) / "morstorm" / "resources"
        target.mkdir(parents=True, exist_ok=True)
        copy2(source, target / source.name)
        copy2(source.with_name("thunderstorm.ijm"), target / "thunderstorm.ijm")
        copy2(source.with_name("official_sources.lock.json"), target / "official_sources.lock.json")
        matlab = Path(__file__).parent / 'matlab'
        for path in matlab.rglob('*.m'):
            destination = target / 'matlab' / path.relative_to(matlab)
            destination.parent.mkdir(parents=True, exist_ok=True)
            copy2(path, destination)


setup(cmdclass={"build_py": BuildPy})
