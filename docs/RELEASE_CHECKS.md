# Release candidate checks

## 0.6.0-rc.1

On Windows, all 30 unit and integration tests passed. The preset tests covered all 16 audit templates, a custom macro expression, engine-independent job settings, and rejection of changes to fixed AIM settings. The English and Chinese desktops were exercised through all seven panels, including an edit, save, restore, import, and engine switch.

Custom ThunderSTORM detection settings completed TIFF localization. Picasso's `sigmaxy` model, tolerance `0.002`, and iteration limit `75` were verified in the localization metadata from B Python and A MATLAB. On the 960-localization demo, a shared custom MeanShift and MorphoLibJ configuration completed in A MATLAB, A Python, and B Python. The maximum drift difference was `4.981e-11 nm` for that configuration.

## 0.5.0-rc.1

The candidate was exercised locally on Windows x64 with Python 3.10.16. The A and B package suites passed 12 tests each, including real ThunderSTORM, Picasso and MorphoLibJ integrations. The release test suite checked synthetic 2D and 3D MeanShift parity, the expected rank-boundary refusals, failure on missing or changed providers, and portable GUI profiles.

| Runtime check | Result |
| --- | --- |
| Public B wheel, no MATLAB or Java on PATH | Synthetic 960-localization drift example completed |
| A wheel and external pinned sources | Author MeanShift matched the 2D reference at export precision |
| Optional local B providers | AIM, NP-Cloud and RR-NP Cloud passed 2D and 3D reference cases, maximum error 2.437e-5 nm |
| English workspace | B drift completed on the synthetic table |
| Chinese workspace | A MATLAB drift and MorphoLibJ completed on the synthetic table |
| Author source verification | All three pinned releases matched their file locks |

Both wheels were built and installed in an isolated target directory. The public tree and wheel checks verified the resource inventory and checked for lab datasets, local providers and workstation paths. GitHub-hosted CI is configured for Windows and Linux and is first exercised when the review branch is pushed.
