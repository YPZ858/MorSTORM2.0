# Validation and scope

## Reproducible public checks

The public fixtures are synthetic. The test suite compares 2D and 3D B MeanShift against frozen results from the pinned author release on MATLAB R2021a. The numerical gate is a maximum absolute error of 0.01 nm over all frames and axes. Two forced outlier cases exercise the rank-boundary refusal and are counted separately. The tests also verify missing-provider behavior, the coordinate format, render checks, file discovery and wheel resources.

```text
python scripts/check_public_tree.py
python -m unittest discover -s tests -v
python -m unittest discover -s MorSTORM-B/tests -v
python -m unittest discover -s MorSTORM-dual/tests -v
```

Set `MORSTORM_FIJI` to run optional real Java integrations. Set `MORSTORM_PICASSO=1` when Picasso is installed. A author runs require MATLAB and the pinned sources. The build workflow creates artifacts for review and the test workflow exercises Python 3.10 on Windows and Linux.

## Scope of the earlier acquisition audit

The acquisition audit used a 6,000-frame TIFF with provisional camera calibration. Initial settings completed 16 of 24 runs. Dataset-specific settings then passed all eight localizer and drift-method pairs across A MATLAB, A Python and B Python, with a largest accepted difference of 0.00370909 nm. This evidence used the local B providers for AIM and NP-Cloud. Seven of eight accepted pairs had exact A/B morphology outputs. The accepted Picasso MeanShift pair differed at 20 foreground pixels. The weighted ThunderSTORM MeanShift retest differed by 7.31963 nm, traced to a confidence-interval decision near a fit bound. The shared profiles use unweighted MeanShift. The real acquisition and its output files stay in the laboratory workspace.

Drift parity compares the same method and input across runtimes. Physical drift accuracy needs an independent experimental reference. MorphoLibJ measurements refer to an XY projection. New samples can require different localization and segmentation settings.
