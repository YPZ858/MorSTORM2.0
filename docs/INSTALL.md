# Installation

## Supported setup

The pinned validation environment is Python 3.10 on Windows x64. B's core CLI has a Windows and Linux CI matrix. A's pinned author binaries and the desktop integration were tested on Windows with MATLAB R2021a and Fiji. AIM and MeanShift need the author MEX builds for the selected platform. The GUI needs Tk, which is included in the standard Windows Python installation. The GUI runs from the repository checkout.

## Create the Python environment

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-py310.txt ./MorSTORM-dual ./MorSTORM-B
```

To localize raw TIFF with Picasso, install the matching optional dependency. Already-localized Picasso HDF5 files can be read without the optional localizer.

```powershell
.\.venv\Scripts\python.exe -m pip install -c constraints-py310.txt './MorSTORM-B[picasso]'
```

## Configure Fiji and A

Install [Fiji](https://fiji.sc/) and enable the MorphoLibJ update site or install its plugin JAR. Install the [ThunderSTORM plugin](https://github.com/zitmen/thunderstorm) in the Fiji `plugins/` directory for ThunderSTORM fitting, post-fitting, or reconstruction. Enter or browse to the Fiji application folder at the top of the workspace. The workspace saves the path when you leave the field or press Enter. You can also configure the paths from the repository root.

```powershell
.\.venv\Scripts\python.exe scripts/configure.py --fiji 'C:/path/to/Fiji.app'
.\MorSTORM-dual\scripts\install_official.ps1
.\MorSTORM-dual\scripts\install_official.ps1 -VerifyOnly
.\.venv\Scripts\python.exe scripts/configure.py --matlab 'C:/path/to/MATLAB/bin/matlab.exe'
```

A's author installer contacts the upstream GitHub and Zenodo archives and checks the original file hashes. NP-Cloud's upstream archive is about 188 MB. `-TargetDir` can place the original releases elsewhere. If you use that option, pass the same directory to `scripts/configure.py --author-root`. These local settings are ignored by Git.

## Start the desktop workspace

Double-click `Start-English.cmd` or `Start-Chinese.cmd`, or run `python gui/app.py --lang en` from the configured environment. Select variant A or B at the top. Choose localization to start with a single-channel TIFF stack. With localization unchecked, select a table for drift and/or morphology. File folders are scanned at one level. Picasso multipart stacks should be exported as one stack per acquisition before using folder mode.

Use **Import localizations…** to select a ThunderSTORM CSV or a Picasso HDF5 and enable **ThunderSTORM reconstruction**. Enter the camera pixel size and set the reconstruction pixel size in its **Advanced…** panel. The original plugin writes `thunderstorm-reconstruction.tif`. The manifest records the XY origin in nm. For ThunderSTORM CSV with `x [px]` and `y [px]`, the camera pixel size converts XY to nm. A Z column labeled in nm retains its scale.

With **Fit TIFF movie** enabled, use **Crop by percentage…** beside the input field to keep a centered 75%, 50%, or 25% of the width and height, or enter custom XY edges as percentages from the top-left corner. The crop applies to every frame. Folder mode calculates the pixel bounds from each file’s dimensions. The result folder contains `raw-cropped.tif`, and the manifest records the requested percentages and the actual pixel bounds. Localization tables use the original image’s XY origin. Presets save the percentages for reuse. The cropped stack must fit within the standard TIFF size limit of about 4 GiB.

The workflow runs TIFF fitting, drift correction, post-fitting, ThunderSTORM reconstruction, then MorphoLibJ. With TIFF fitting off, **Table backend** chooses the backend for **Post-fitting**. ThunderSTORM offers a quality expression, same-frame duplicate removal, local density filtering, and merging. To recalculate uncertainty during Merge, the imported fitting table needs sigma, intensity in photons, and `bkgstd` in photons. New ThunderSTORM fits export these fields. Picasso post-fitting accepts the HDF5 and its matching YAML, filters by photons and XY uncertainty, and offers the original Picasso Link. Enable each desired operation in the **Advanced…** panel. Output tables use `postfit.csv` or `postfit.hdf5` plus `postfit.yaml`.

Use **Stop** to cancel an active job. The batch report records completed, failed, cancelled, and unstarted files. **Exit** offers to stop an active job before closing. After a batch with a completed file, choose whether to save its parameters. **Load last parameters** reopens the saved preset, including stage selections and algorithm settings.

Use **Advanced…** beside an enabled stage to open the panel for the selected algorithm. The **Audit default** column shows the preset used in the original validation and the adapter defaults for options omitted by that preset. The note above the table describes fixed settings. In ThunderSTORM, named controls are passed as ImageJ macro options. Use the additional options fields for other filter or fitter settings from your plugin. Leave an optional field blank to omit it.

**Save preset as…** writes a schema-1 JSON file with the selected stages and algorithm settings. **Import preset…** accepts these files, the templates under `profiles/`, and compatible `run-config.json` files from earlier GUI runs. The workspace uses its own dependency paths and its current A/B selection. Select the input file or folder for the new run in the main window. **Restore audit values** reloads the audit settings for the selected workflow and clears custom edits across the panels.

For a local Fiji test using the synthetic CSV, select B and MeanShift, uncheck localization, select `MorSTORM-B/examples/demo_thunderstorm.csv`, set the camera pixel to `160` and the MeanShift time bins to `8`. Morphology uses Fiji if selected. Each run writes a fresh result directory under the chosen parent.

## Use the CLI and MATLAB

`morstorm` is A's Python CLI and `morstorm-b` is B's CLI. Both accept a schema-1 JSON configuration. Use the complete examples in each package, or copy a template under `profiles/` and enter the dataset and dependency paths. JSON paths are relative to the config directory. GUI settings apply to the GUI, while direct CLI configs carry their own `morphology.fiji_dir`, `localization.fiji_dir` and `drift.official` settings.

```powershell
.\.venv\Scripts\morstorm-b.exe MorSTORM-B/examples/drift-only.json --output ../../results/b-repeat
```

For direct A MATLAB, add `MorSTORM-dual/matlab` to the MATLAB path and call `morstorm.run(configPath)`. A MATLAB's Picasso localizer needs `localization.python_executable` pointing to a Python environment with `morstorm` and `picassosr` installed. Set an absolute `drift.official.root` and `drift.official.matlab_executable` if running an A JSON outside the usual project layout.

Use the GUI modules when only localization or morphology is needed. Their per-file `run-config.json` records the chosen stage list and resolved input paths. For B NP-Cloud and AIM, see [local providers](LOCAL_PROVIDERS.md).
