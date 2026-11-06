from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from morstorm_b.drift import estimate
from morstorm_b.native.common import ParityDomainError


ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def test_synthetic_author_parity(self):
        fixtures = ROOT/'MorSTORM-B/tests/golden'
        manifest = json.loads((fixtures/'cases.json').read_text(encoding='utf-8'))
        for case in manifest['cases']:
            with self.subTest(case=case['name']):
                path = fixtures/case['file']
                self.assertEqual(sha256(path.read_bytes()).hexdigest(),case['sha256'])
                with np.load(path,allow_pickle=False) as data:
                    columns = ['frame','x_nm','y_nm']+(['z_nm'] if case['dimensions']==3 else [])
                    table = pd.DataFrame(data['localizations'],columns=columns)
                    config = {**case['config'],'method':'meanshift'}
                    if 'meanshift' in case['expected_rejections']:
                        with self.assertRaises(ParityDomainError):
                            estimate(table,config)
                    else:
                        curve,metadata = estimate(table,config)
                        self.assertFalse(metadata['matlab_required'])
                        self.assertLessEqual(np.max(np.abs(curve-data['meanshift'])),.01)

    def test_missing_and_mismatched_optional_providers(self):
        table = pd.DataFrame({'frame':[1,2],'x_nm':[100,101],'y_nm':[200,201]})
        with tempfile.TemporaryDirectory() as temp, patch.dict('os.environ',{'MORSTORM_B_LOCAL_PROVIDERS':temp}):
            for method in ('aim','npcloud','rrnpcloud'):
                with self.assertRaisesRegex(RuntimeError,'requires a local provider'):
                    estimate(table,{'method':method})
            (Path(temp)/'aim.py').write_text('raise AssertionError("unverified code was executed")',encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError,'checksum'):
                estimate(table,{'method':'aim'})

    def test_gui_profiles_are_portable(self):
        spec = importlib.util.spec_from_file_location('release_gui_runner',ROOT/'gui/runner.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with patch.dict('os.environ',{'MORSTORM_SETTINGS':str(ROOT/'absent-test-settings.json')}):
            for mode in ('raw','cached'):
                for backend in runner.BACKENDS:
                    for method in runner.METHODS.values():
                        profile = runner.load_profile(mode,backend,method)
                        self.assertIsNone(profile.source)
                        self.assertEqual(Path(profile.config['drift']['official']['root']),ROOT/'MorSTORM-dual/third_party')
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            for name in ('a.csv','B.h5','ignored.tif'):
                (temp/name).touch()
            profile = runner.load_profile('cached','ThunderSTORM','meanshift')
            job = runner.make_job(profile,'B Python',str(temp),True,('drift',),str(temp/'results'),'160','8',{},'10')
            self.assertEqual([p.name for p in runner.inputs(job)],['a.csv','B.h5'])


if __name__=='__main__':
    unittest.main()
