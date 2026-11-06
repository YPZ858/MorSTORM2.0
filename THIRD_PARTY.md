# Sources and distribution scope

The proposed license for the newly authored integration and the shipped MeanShift adaptation is GPL-3.0-or-later. The accompanying `LICENSE` contains the GPL v3 text. See the release review before publishing the candidate.

| Component | Source | Distribution in this candidate |
| --- | --- | --- |
| Original MorSTORM | [YPZ858/MorSTORM](https://github.com/YPZ858/MorSTORM) | Attribution and links. The original MATLAB script, manual, ZIP and TIFF are separate from this candidate. |
| MeanShift | [VeatchLab, b04d42f0d099cab9b6cd0c184eb0551a41d6664a](https://github.com/VeatchLab/Mean-Shift-Drift-Correction/tree/b04d42f0d099cab9b6cd0c184eb0551a41d6664a) | Copyright (C) 2021 Frank Fazekas, Thomas Shaw, and Sarah Veatch. The B adaptation changes the implementation language and bounded fitting engine. GPL-3.0-or-later. A fetches the pinned source separately. |
| NP-Cloud and RR-NP Cloud | [Hou et al., Zenodo 16513620](https://doi.org/10.5281/zenodo.16513620) and [paper](https://doi.org/10.1038/s41467-025-64085-8) | A fetches the pinned release. The local B adaptation and the published simulation are outside this distribution. The upstream record uses [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). |
| AIM | [Ma, Chen, Nguyen and Liu, a6e86b58828f8f2b42ec421ef5681d4e7ca9ce3c](https://github.com/YangLiuLab/AIM/tree/a6e86b58828f8f2b42ec421ef5681d4e7ca9ce3c) | A fetches the pinned release. The pinned tree has no top-level license. The author files and local B adaptation are outside this distribution. |
| ThunderSTORM | [ThunderSTORM](https://github.com/zitmen/thunderstorm) | Installed by the user as a Fiji plugin. |
| Picasso | [Picasso](https://github.com/jungmannlab/picasso) | Optional Python dependency. |
| ImageJ and MorphoLibJ | [ImageJ](https://imagej.net/ij/) and [MorphoLibJ](https://github.com/ijpb/MorphoLibJ) | User-installed runtime. The small MorSTORM JAR contains the two bridge classes, with corresponding Java sources and a rebuild script. |

The A installer verifies original files against `MorSTORM-dual/shared/official_sources.lock.json`. The public MeanShift fixtures contain synthetic localization coordinates and previously generated author output curves. Their inputs do not come from the lab TIFF or the Zenodo simulation.
