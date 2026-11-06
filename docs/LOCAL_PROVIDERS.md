# Optional local B providers

The standalone B release includes MeanShift, an identity mode and external drift CSV input. NP-Cloud, RR-NP Cloud and AIM can use the checksum-matched ports from an existing local MorSTORM B 0.4.0 archive or wheel. The candidate contains the provider interface and SHA-256 lock. Install only a package you already have and are permitted to use. The installer reads a local path and does not fetch a package.

```powershell
.\.venv\Scripts\python.exe scripts/install_local_b.py 'C:/path/to/MorSTORM-B-v0.4.0-standalone.zip'
$env:MORSTORM_B_LOCAL_PROVIDERS = (Resolve-Path local_backends/b).Path
```

The installer accepts `--provider aim` or `--provider npcloud` to select one. `npcloud.py` supplies both NP-Cloud modes. Use `--target` for an alternate directory, then either set `MORSTORM_B_LOCAL_PROVIDERS` for the CLI or configure `--b-providers` for the GUI. The GUI discovers the default `local_backends/b/` automatically. B verifies each file before loading and does not switch algorithms on a missing or changed provider.

For users without that local package, the A version can access these algorithms through the original author releases, or either Python CLI can consume an external drift curve using `external_csv`. See [distribution scope](../THIRD_PARTY.md) and [installation](INSTALL.md).
