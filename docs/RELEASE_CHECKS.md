# Release candidate checks

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
