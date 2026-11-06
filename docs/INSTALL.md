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

Install [Fiji](https://fiji.sc/) and enable the MorphoLibJ update site or install its plugin JAR. Install the [ThunderSTORM plugin](https://github.com/zitmen/thunderstorm) in the Fiji `plugins/` directory if using that localizer. Configure the paths from the repository root.

```powershell
.\.venv\Scripts\python.exe scripts/configure.py --fiji 'C:/path/to/Fiji.app'
.\MorSTORM-dual\scripts\install_official.ps1
.\MorSTORM-dual\scripts\install_official.ps1 -VerifyOnly
.\.venv\Scripts\python.exe scripts/configure.py --matlab 'C:/path/to/MATLAB/bin/matlab.exe'
```

A's author installer contacts the upstream GitHub and Zenodo archives and checks the original file hashes. NP-Cloud's upstream archive is about 188 MB. `-TargetDir` can place the original releases elsewhere. If you use that option, pass the same directory to `scripts/configure.py --author-root`. These local settings are ignored by Git.

## Start the desktop workspace

Double-click `Start-English.cmd` or `Start-Chinese.cmd`, or run `python gui/app.py --lang en` from the configured environment. Select variant A or B at the top. Choose localization to start with a single-channel TIFF stack. With localization unchecked, select a table for drift and/or morphology. File folders are scanned at one level. Picasso multipart stacks should be exported as one stack per acquisition before using folder mode.

For a local Fiji test using the synthetic CSV, select B and MeanShift, uncheck localization, select `MorSTORM-B/examples/demo_thunderstorm.csv`, set the camera pixel to `160` and the MeanShift time bins to `8`. Morphology uses Fiji if selected. Each run writes a fresh result directory under the chosen parent.

## Use the CLI and MATLAB

`morstorm` is A's Python CLI and `morstorm-b` is B's CLI. Both accept a schema-1 JSON configuration. Use the complete examples in each package, or copy a template under `profiles/` and enter the dataset and dependency paths. JSON paths are relative to the config directory. GUI settings apply to the GUI, while direct CLI configs carry their own `morphology.fiji_dir`, `localization.fiji_dir` and `drift.official` settings.

```powershell
.\.venv\Scripts\morstorm-b.exe MorSTORM-B/examples/drift-only.json --output ../../results/b-repeat
```

For direct A MATLAB, add `MorSTORM-dual/matlab` to the MATLAB path and call `morstorm.run(configPath)`. A MATLAB's Picasso localizer needs `localization.python_executable` pointing to a Python environment with `morstorm` and `picassosr` installed. Set an absolute `drift.official.root` and `drift.official.matlab_executable` if running an A JSON outside the usual project layout.

Use the GUI modules when only localization or morphology is needed. Their per-file `run-config.json` records the chosen stage list and resolved input paths. For B NP-Cloud and AIM, see [local providers](LOCAL_PROVIDERS.md).
