from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

import numpy as np
import tifffile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'gui'))
import parameters
import raw_crop
import runner


class ParameterPresets(unittest.TestCase):
    def test_percent_crop_preserves_frames_and_restores_coordinates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root/'source.tif', root/'raw-cropped.tif'
            movie = np.arange(3*9*11, dtype=np.uint16).reshape(3, 9, 11)
            tifffile.imwrite(source, movie, photometric='minisblack', compression='deflate', metadata={'axes': 'TYX'})
            profile = runner.load_profile('raw', 'ThunderSTORM', 'meanshift')
            profile.config['raw_crop'] = {'left': 20, 'top': 25, 'right': 70, 'bottom': 75}
            preset = root/'preset.json'
            runner.save_json(preset, parameters.export_preset(profile, ('localize',), 100, 8, 10))
            restored, _ = parameters.import_preset(preset, 'ThunderSTORM')
            applied = raw_crop.crop_tiff(source, target, restored.config['raw_crop'], lambda: False, 100)
            np.testing.assert_array_equal(tifffile.imread(target), movie[:, 2:7, 2:8])
            np.testing.assert_array_equal(tifffile.imread(source), movie)
            self.assertEqual(applied['bounds_xyxy_px'], [2, 2, 8, 7])
            self.assertEqual(applied['frames'], 3)

            table = root/'localized.csv'
            table.write_text('frame,x [nm],y [nm],z [nm]\n2,15,25,35\n', encoding='utf-8')
            raw_crop.restore_localizations(table, applied)
            from morstorm_b.io import read_localizations
            row = read_localizations(table, {}).table.iloc[0]
            self.assertEqual(tuple(row), (2, 215, 225, 35))

            table.write_text('id\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'no localizations in the cropped TIFF'):
                raw_crop.restore_localizations(table, applied)
            self.assertEqual(table.read_text(encoding='utf-8'), 'id\n')
            self.assertFalse(table.with_suffix('.csv.partial').exists())

    def test_import_and_postfit_preset_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'table.csv'
            source.write_text('frame,x [px],y [px],z [nm]\n1,2,3,45\n', encoding='utf-8')
            profile = runner.load_profile('cached', 'ThunderSTORM', 'meanshift')
            panel = 'ThunderSTORM postfit'
            parameters.set_values(profile.config, panel, {**parameters.values(profile.config, panel),
                                                          'density': True, 'merge': True, 'merge_nm': 35})
            modules = ('postfit', 'reconstruct')
            saved = root / 'preset.json'
            runner.save_json(saved, parameters.export_preset(profile, modules, 100, 8, 10))
            restored, stages = parameters.import_preset(saved, 'Picasso')
            job = runner.make_job(restored, 'B Python', str(source), False, stages, directory, 100, 8, None, 10)
            config = runner.file_config(job, source, root)
            self.assertEqual(job.modules, modules)
            self.assertEqual(config['postfit']['merge_nm'], 35)
            from morstorm_b.io import read_localizations
            table = read_localizations(source, config['input']).table
            self.assertEqual(tuple(table.iloc[0][['x_nm', 'y_nm', 'z_nm']]), (200, 300, 45))

    def test_cancelled_batch_preserves_completed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('a.csv', 'b.csv', 'c.csv'):
                (root/name).touch()
            profile = runner.load_profile('cached', 'ThunderSTORM', 'meanshift')
            job = runner.make_job(profile, 'B Python', str(root), True, ('drift',), directory, 100, 8, None, 10)
            cancel = Event()

            def run_item(_job, source, _folder, _notify, _cancel):
                if source.name == 'b.csv':
                    cancel.set()
                    raise runner.JobCancelled()
                return {'localizations': 3, 'last_frame': 3}

            with patch.object(runner, 'check_dependencies'), patch.object(runner, 'run_item', side_effect=run_item):
                runner.run(job, lambda *_: None, cancel)
            report = json.loads((job.output/'batch-report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['status'], 'cancelled')
            self.assertEqual((report['completed'], report['failed'], report['cancelled'], report['unstarted']), (1, 0, 1, 1))

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
