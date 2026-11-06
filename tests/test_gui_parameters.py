from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'gui'))
import parameters
import runner


class ParameterPresets(unittest.TestCase):
    def test_audit_profiles_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'preset.json'
            for mode in ('raw', 'cached'):
                for backend in runner.BACKENDS:
                    for method in runner.METHODS.values():
                        with self.subTest(mode=mode, backend=backend, method=method):
                            profile = runner.load_profile(mode, backend, method)
                            modules = runner.MODULES if mode == 'raw' else runner.MODULES[1:]
                            saved = parameters.export_preset(profile, modules, '103.5', profile.period, '10')
                            runner.save_json(path, saved)
                            restored, selected = parameters.import_preset(path, 'Picasso')
                            self.assertEqual(selected, modules)
                            self.assertEqual(restored.period, profile.period)
                            self.assertEqual(restored.backend, backend)
                            panels = (backend, method, 'morphology') if mode == 'raw' else (method, 'morphology')
                            for panel in panels:
                                old = parameters.values(profile.config, panel)
                                new = parameters.values(restored.config, panel)
                                for field in parameters.FIELDS[panel]:
                                    self.assertEqual(parameters.parse_field(field, old.get(field.key)),
                                                     parameters.parse_field(field, new.get(field.key)), field.key)

    def test_custom_thunderstorm_preset_reaches_every_engine(self):
        profile = runner.load_profile('raw', 'ThunderSTORM', 'meanshift')
        camera = parameters.values(profile.config, 'ThunderSTORM')
        camera.update(threshold='mean(Wave.F1) + 2*std(Wave.F1)', sigma=1.6,
                      extra_analysis='nmax=3 keep_same_intensity=false')
        parameters.set_values(profile.config, 'ThunderSTORM', camera)
        drift = parameters.values(profile.config, 'meanshift')
        parameters.set_values(profile.config, 'meanshift', {**drift, 'nTimeBin': 9, 'rmax': 460, 'outlier_error': 240})
        morph = parameters.values(profile.config, 'morphology')
        parameters.set_values(profile.config, 'morphology', {**morph, 'threshold': .35, 'exclude_border': True})
        config = parameters.export_preset(profile, runner.MODULES, 110, 9, 12)
        self.assertNotIn('official', config['drift'])
        self.assertNotIn('fiji_dir', config['localization'])
        self.assertNotIn('execution_engine', config)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'preset.json'
            runner.save_json(path, config)
            restored, modules = parameters.import_preset(path, 'Picasso')
            jobs = [runner.make_job(restored, engine, 'movie.tif', False, modules, directory, 110, 9, None, 12)
                    for engine in runner.ENGINES]
        baseline = dict(jobs[0].config)
        baseline.pop('execution_engine')
        for job in jobs:
            self.assertEqual({key: value for key, value in job.config.items() if key != 'execution_engine'}, baseline)
        analysis = parameters.macro_options(baseline['localization']['analysis_options'])
        self.assertEqual(analysis['threshold'], camera['threshold'])
        self.assertEqual(analysis['sigma'], '1.6')
        self.assertEqual(analysis['nmax'], '3')
        self.assertEqual(baseline['drift']['parameters']['meanshift']['outlier_error'], 240)
        self.assertTrue(baseline['morphology']['exclude_border'])

    def test_legacy_cached_preset_and_invalid_values(self):
        config = deepcopy(runner.load_profile('cached', 'Picasso', 'aim').config)
        config['input']['pixel_size_nm'] = 117
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'preset.json'
            path.write_text(json.dumps(config), encoding='utf-8')
            profile, _ = parameters.import_preset(path, 'ThunderSTORM')
            self.assertEqual(profile.backend, 'Picasso')
            self.assertEqual(profile.config['input']['pixel_size_nm'], 117)
            config['drift']['radius_nm'] = 75
            path.write_text(json.dumps(config), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'fixed'):
                parameters.import_preset(path, 'ThunderSTORM')
        profile = runner.load_profile('raw', 'Picasso', 'meanshift')
        fields = parameters.values(profile.config, 'Picasso')
        with self.assertRaisesRegex(ValueError, 'odd'):
            parameters.set_values(profile.config, 'Picasso', {**fields, 'box_size': 8})


if __name__ == '__main__':
    unittest.main()
