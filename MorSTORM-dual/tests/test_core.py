import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
import h5py
import numpy as np
import pandas as pd
import tifffile
from morstorm.io import read_localizations, write_exports, Localizations
from morstorm.drift import estimate
from morstorm.pipeline import render, run

ROOT = Path(__file__).resolve().parents[1]


class Contracts(unittest.TestCase):
    def test_thunderstorm_units_and_extra_fields(self):
        locs = read_localizations(ROOT / "examples/demo_thunderstorm.csv", {})
        self.assertEqual(list(locs.table)[:3], ["frame", "x_nm", "y_nm"])
        self.assertEqual(locs.table.frame.iloc[0], 1)
        self.assertIn("uncertainty [nm]", locs.table)
        self.assertLess(locs.table.x_nm.min(), 0)

    def test_ambiguous_csv_rejected_and_explicit_pixel_map(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "locs.csv"
            path.write_text("f,x,y\n0,2,3\n", encoding="utf-8")
            with self.assertRaises(ValueError): read_localizations(path, {})
            cfg = {"columns": {"frame": "f", "x_nm": "x", "y_nm": "y"},
                   "coordinate_unit": "pixel", "pixel_size_nm": 100, "frame_base": 0}
            t = read_localizations(path, cfg).table
            np.testing.assert_equal(t[["frame", "x_nm", "y_nm"]].to_numpy(), [[1, 200, 300]])

    def test_picasso_xy_pixel_z_nm_row_order_and_roundtrip(self):
        records = np.array([(7, 2., 3., -75., 500.), (0, 4., 5., 20., 600.)],
                           dtype=[("frame", "u4"), ("x", "f4"), ("y", "f4"), ("z", "f4"), ("photons", "f4")])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "locs.hdf5"
            with h5py.File(path, "w") as h: h["locs"] = records
            locs = read_localizations(path, {"pixel_size_nm": 100})
            np.testing.assert_equal(locs.table[["frame", "x_nm", "y_nm", "z_nm"]].to_numpy(), [[8, 200, 300, -75], [1, 400, 500, 20]])
            locs.table.x_nm -= 10
            write_exports(locs, temp)
            with h5py.File(Path(temp) / "picasso_corrected.hdf5") as h: corrected = h["locs"][:]
            np.testing.assert_equal(corrected["frame"], records["frame"])
            np.testing.assert_equal(corrected["photons"], records["photons"])
            np.testing.assert_allclose(corrected["x"], records["x"] - .1)
            np.testing.assert_equal(corrected["z"], records["z"])

    def test_histogram_has_all_points_and_negative_origin(self):
        t = pd.DataFrame({"frame": [1]*4, "x_nm": [-10., 0., 10., 10.], "y_nm": [-20., 0., 20., 20.]})
        image, meta = render(t, {"pixel_size_nm": 10})
        self.assertEqual(image.sum(), 4)
        np.testing.assert_equal(meta["origin_nm"], [-20, -30])
        self.assertEqual(image[5, 3], 2)
        with self.assertRaises(ValueError): render(t, {"pixel_size_nm": 1, "max_pixels": 10})

    def test_invalid_localizations_rejected(self):
        for f, x in ((0, 1), (1.5, 1), (1, np.nan)):
            with self.assertRaises(ValueError):
                Localizations(pd.DataFrame({"frame": [f], "x_nm": [x], "y_nm": [1]})).validate()


class Drift(unittest.TestCase):
    def test_external_curve_and_input_validation(self):
        table = read_localizations(ROOT / "examples/demo_thunderstorm.csv", {}).table
        curve, _ = estimate(table, {"method":"external_csv", "path":ROOT / "examples/demo_drift.csv"})
        np.testing.assert_allclose(curve, pd.read_csv(ROOT / "examples/demo_drift.csv").iloc[:,1:].to_numpy())
        with self.assertRaises(ValueError): estimate(table, {"method":"reference-npcloud"})
        bad = table.copy(); bad.loc[bad.index[0], "frame"] = 0
        with self.assertRaises(ValueError): estimate(bad, {"method":"none"})

    def test_author_methods_cannot_be_overridden(self):
        from morstorm import register_drift
        for name in ("meanshift","npcloud","rrnpcloud","aim"):
            with self.assertRaises(ValueError): register_drift(name, lambda t,c: None)


class Pipeline(unittest.TestCase):
    def test_explicit_method_and_output_override(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg={'input':{'path':str(ROOT/'examples/demo_thunderstorm.csv')},
                 'drift':{'method':'unknown'},'morphology':{'enabled':False},
                 'output_dir':str(Path(temp)/'unused')}
            out=Path(temp)/'override'
            manifest=run(cfg,method='none',output_dir=out)
            self.assertEqual(manifest['status'],'preprocessing_only')
            self.assertEqual(manifest['drift']['method'],'none')
            self.assertTrue((out/'corrected.csv').is_file())
            self.assertFalse(Path(cfg['output_dir']).exists())

    def test_failed_run_records_error_and_existing_output_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg = {"input": {"path": str(ROOT / "examples/demo_thunderstorm.csv")},
                   "drift": {"method": "unknown"}, "output_dir": str(Path(temp) / "run")}
            with self.assertRaises(ValueError): run(cfg)
            manifest = json.loads((Path(cfg["output_dir"]) / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "failed")
            with self.assertRaises(FileExistsError): run(cfg)

    @unittest.skipUnless(os.environ.get("MORSTORM_FIJI"), "Set MORSTORM_FIJI for real MorphoLibJ integration")
    def test_actual_morpholibj_and_empty_masks(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg = json.loads((ROOT / "examples/demo.json").read_text())
            cfg["input"]["path"] = str(ROOT / "examples/demo_thunderstorm.csv")
            cfg["drift"] = {"method":"none"}
            cfg["morphology"]["fiji_dir"] = os.environ["MORSTORM_FIJI"]
            cfg["output_dir"] = str(Path(temp) / "含 空格")
            m = run(cfg)
            self.assertEqual(m["status"], "complete")
            table = pd.read_csv(Path(cfg["output_dir"]) / "morphology.csv")
            self.assertEqual(len(table), 12)
            self.assertEqual(table.LocalizationCount.sum(), 960)
            assignments = pd.read_csv(Path(cfg["output_dir"]) / "assignments.csv")
            self.assertEqual(len(assignments), 960)
            self.assertTrue((assignments.label > 0).all())
            self.assertTrue((table.Area > 0).all())
            self.assertLess(table["Centroid.X"].min(), -280)
            self.assertGreater(table["Centroid.Y"].min(), 380)
            labels = tifffile.imread(Path(cfg["output_dir"]) / "labels.tif")
            rendering = json.loads((Path(cfg["output_dir"]) / "render.json").read_text())
            for _, row in table.iterrows():
                yy, xx = np.nonzero(labels == row.ObjectLabel)
                self.assertAlmostEqual(row.Area, len(xx) * 100)
                self.assertAlmostEqual(row["Centroid.X"], (xx.mean() + .5) * 10 + rendering["origin_nm"][0], places=8)
                self.assertAlmostEqual(row["Centroid.Y"], (yy.mean() + .5) * 10 + rendering["origin_nm"][1], places=8)
            cfg["morphology"]["threshold"] = 1e10
            cfg["output_dir"] = str(Path(temp) / "empty")
            self.assertEqual(run(cfg)["status"], "complete")
            empty = pd.read_csv(Path(cfg["output_dir"]) / "morphology.csv")
            self.assertEqual(len(empty), 0)
            self.assertEqual(list(empty), list(table))


if __name__ == "__main__": unittest.main(verbosity=2)
