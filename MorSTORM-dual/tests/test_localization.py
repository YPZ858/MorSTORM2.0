"""Optional integration tests call the real installed localization software."""
from pathlib import Path
import os
import tempfile
import unittest
import numpy as np
import tifffile
from morstorm.pipeline import run


class Localization(unittest.TestCase):
    def fixture(self, folder):
        rng = np.random.default_rng(8)
        y, x = np.mgrid[:48, :48]
        image = np.ones((48, 48)) * 100
        for cx, cy in ((12.2, 12.3), (32.4, 13.3), (24.2, 34.5)):
            image += 800 * np.exp(-((x-cx)**2 + (y-cy)**2) / (2*1.3**2))
        movie = rng.poisson(np.broadcast_to(image, (8, 48, 48))).astype(np.uint16)
        p = Path(folder) / "movie.tif"
        tifffile.imwrite(p, movie, photometric="minisblack", metadata=None)
        return p

    @unittest.skipUnless(os.environ.get("MORSTORM_PICASSO"), "Set MORSTORM_PICASSO=1 for upstream MLE")
    def test_picasso_movie_to_canonical(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.fixture(temp)
            cfg = {"input": {"kind": "movie", "path": str(path)},
                   "localization": {"backend": "picasso", "pixel_size_nm": 103.5,
                                    "camera": {"baseline": 100, "sensitivity": 1, "gain": 1},
                                    "box_size": 7, "min_net_gradient": 1000},
                   "drift": {"method": "none"}, "morphology": {"enabled": False},
                   "output_dir": str(Path(temp) / "results")}
            m = run(cfg)
            self.assertEqual(m["status"], "preprocessing_only")
            self.assertEqual(m["localizations"], 24)
            self.assertTrue((Path(cfg["output_dir"]) / "picasso_corrected.hdf5").is_file())

    @unittest.skipUnless(os.environ.get("MORSTORM_FIJI"), "Set MORSTORM_FIJI for real ThunderSTORM")
    def test_thunderstorm_movie_to_morpholibj(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.fixture(temp)
            cfg = {"input": {"kind": "movie", "path": str(path)},
                   "localization": {"backend": "thunderstorm", "fiji_dir": os.environ["MORSTORM_FIJI"],
                                    "timeout_seconds": 90,
                                    "camera_options": "offset=100 isemgain=false photons2adu=1 pixelsize=103.5",
                                    "analysis_options": "filter=[Wavelet filter (B-Spline)] scale=2.0 order=3 detector=[Local maximum] connectivity=8-neighbourhood threshold=1.2*std(Wave.F1) estimator=[PSF: Integrated Gaussian] sigma=1.3 fitradius=3 method=[Weighted Least squares] full_image_fitting=false mfaenabled=false renderer=[No Renderer]"},
                   "drift": {"method": "none"},
                   "morphology": {"enabled": True, "fiji_dir": os.environ["MORSTORM_FIJI"]},
                   "output_dir": str(Path(temp) / "results")}
            m = run(cfg)
            self.assertEqual(m["status"], "complete")
            self.assertEqual(m["localizations"], 24)
            import pandas as pd
            objects = pd.read_csv(Path(cfg["output_dir"]) / "morphology.csv")
            self.assertEqual(len(objects), 3)
            self.assertEqual(objects.LocalizationCount.sum(), 24)


if __name__ == "__main__": unittest.main(verbosity=2)
