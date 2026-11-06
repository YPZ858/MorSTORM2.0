from pathlib import Path
from shutil import copy2
from setuptools import setup
from setuptools.command.build_py import build_py

class BuildPy(build_py):
    def run(self):
        super().run()
        root=Path(__file__).parent;target=Path(self.build_lib)/'morstorm_b/resources'
        target.mkdir(parents=True,exist_ok=True)
        for name in ('morstorm-morphology.jar','thunderstorm.ijm','upstream_sources.lock.json'):
            copy2(root/'shared'/name,target/name)
        copy2(root/'LICENSE',target/'MEANSHIFT-LICENSE.txt')
        copy2(root/'THIRD_PARTY.md',target/'UPSTREAM-NOTICE.md')

setup(cmdclass={'build_py':BuildPy})
