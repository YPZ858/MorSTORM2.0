# Contributing

Install the packages with Python 3.10 and `constraints-py310.txt`. Run `python scripts/check_public_tree.py`, `python -m unittest discover -s tests -v` and each package's `tests` directory. Keep new fixtures synthetic or supply a documented redistribution grant.

State the affected backend, platform, dependency versions, input units, frame convention and parameters in a report or pull request. For changes to drift, include a reference case and report maximum absolute error and RMSE. For changes to morphology, specify the render grid and what was compared in the label image, object table and assignments. Review English and Chinese labels together when changing the workspace.

Keep lab images, private logs, account paths, local settings, author MEX files and local B providers out of commits. The issue template accepts reduced synthetic reproductions. Add attribution and terms in `THIRD_PARTY.md` for any new upstream material.
