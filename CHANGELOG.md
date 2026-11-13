# Changelog

## 0.6.0-rc.2

- Adds percentage-based XY cropping for raw TIFF images and stacks in single-file and folder mode. The same region applies to every frame, and localization coordinates use the original image origin. The result includes the cropped TIFF and the applied bounds.
- Adds an explicit localization-table import and native ThunderSTORM reconstruction. Localization, drift, post-fitting, reconstruction, and MorphoLibJ can run independently or in an ordered workflow.
- Adds native ThunderSTORM filtering, duplicate removal, density filtering, and merge. The Picasso panel exposes photon and precision filters and native Link.
- Adds a persistent Fiji path, Stop, Stop and exit, and an opt-in last-used parameter preset to the English and Chinese workspaces.

## 0.6.0-rc.1

- Adds bilingual parameter panels for Picasso, ThunderSTORM, MeanShift, NP-Cloud, RR-NP Cloud, AIM, and MorphoLibJ. Each panel shows units, active values, audited defaults, and fixed settings.
- Imports and saves shared schema-1 parameter presets. A and B use the same algorithm settings. Restore audit values reloads the original settings for the selected workflow.
- Exposes Picasso MLE tolerance, iteration limit, and Gaussian width model. ThunderSTORM accepts named settings and additional ImageJ macro options.

## 0.5.0-rc.1

- Consolidates the A and B runtimes, the English and Chinese Windows workspace, and shareable JSON profiles.
- Supports independent localization, drift correction and morphology, and all ordered stage combinations for files and folders.
- Ships native B MeanShift. B's NP-Cloud, RR-NP Cloud and AIM selection loads checksum-matched local providers.
- Adds synthetic reference data, CI for the Python packages, an artifact-only build workflow, dependency source locks and reproducibility notes.
- Moves workstation paths into ignored local settings and excludes experimental inputs, upstream binaries and local provider files from release artifacts.
