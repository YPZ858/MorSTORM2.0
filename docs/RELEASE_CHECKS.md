# Release candidate checks

## 0.6.0-rc.2

On Windows, all 33 unit and integration tests passed, including real ThunderSTORM, Picasso, and MorphoLibJ calls. Both desktop languages were checked for Fiji path persistence, crop presets across A/B, direct CSV or HDF5 import and reconstruction, the last-used parameter prompt, and cancellation during localization through Stop or Exit.

The original 561-channel stack from the earlier audit was cropped from 512 × 512 to 256 × 256 pixels and retained all 6,000 frames. Six GUI-runner workflows completed through fitting, drift correction, native post-fitting, ThunderSTORM reconstruction, and MorphoLibJ. The batch-mode run used B Python and ThunderSTORM. Fitted coordinates were restored to the original image origin, and sampled frame pixels matched the source region.

| Fitter | Runtime | Drift method | Fitted rows | Post-fitting rows | Regions |
| --- | --- | --- | ---: | ---: | ---: |
| ThunderSTORM | A MATLAB | MeanShift | 3,466 | 695 | 48 |
| ThunderSTORM | A Python | NP-Cloud | 3,466 | 696 | 54 |
| ThunderSTORM | B Python | RR-NP Cloud | 3,466 | 698 | 57 |
| Picasso | A MATLAB, A Python, B Python | AIM | 72,244 each | 66,917 each | 2,775 each |

The ThunderSTORM crop had detections through frame 5,978. The drift output covered frames 1–5,978. Picasso had detections through frame 6,000. The full-field NP-Cloud radii (0.45 and 0.3375 camera pixels) produced an empty cloud in the cropped ThunderSTORM data. The two cloud methods completed with radii of 1.25 and 0.9375 camera pixels and the original 600-frame segments. The published audit presets retain their full-field values.

On identical fitted input for each comparison, the maximum absolute A/B drift errors were 2.67e-15 nm (MeanShift), 1.14e-13 nm (NP-Cloud), 3.09e-6 nm (RR-NP Cloud), and 4.99e-9 nm (AIM, across both A entry points). The AIM reconstruction TIFFs, label images, and assignments matched across all three runtimes. The acquisition and its derived outputs are kept locally.

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
