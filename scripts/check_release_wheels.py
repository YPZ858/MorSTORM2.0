"""Verify wheel payloads, version, license and bundled resources."""
from pathlib import Path
from io import BytesIO
import sys
from zipfile import ZipFile


def main(directory):
    wheels = sorted(Path(directory).glob('morstorm*-0.5.0rc1-*.whl'))
    assert len(wheels)==2, wheels
    for path in wheels:
        package = 'morstorm_b' if path.name.startswith('morstorm_standalone-') else 'morstorm'
        with ZipFile(path) as wheel:
            assert wheel.testzip() is None
            names = set(wheel.namelist())
            assert f'{package}/resources/morstorm-morphology.jar' in names
            with ZipFile(BytesIO(wheel.read(f'{package}/resources/morstorm-morphology.jar'))) as bridge:
                assert set(bridge.namelist())=={'MorstormMorphology.class','MorstormThunderstorm.class'}
            assert any(name.endswith('/LICENSE') for name in names)
            assert not any(name.endswith(('native/aim.py','native/npcloud.py','.mexw64','.tiff','.mat')) for name in names)
            if package=='morstorm_b':
                assert f'{package}/native/providers.json' in names
                assert f'{package}/native/meanshift.py' in names
                assert not any(name.endswith('.m') for name in names)
            else:
                assert f'{package}/resources/matlab/+morstorm/official_drift.m' in names
        print(f'Verified {path.name}')


if __name__=='__main__':
    main(sys.argv[1])
