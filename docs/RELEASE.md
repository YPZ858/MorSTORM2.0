# GitHub release review

Candidate tag `v0.5.0-rc.1`. Both Python distributions use the PEP 440 version `0.5.0rc1`.

1. Confirm the repository owner and release destination. Use the original project only if its maintainer wants this as an extension release, or create a separately attributed repository.
2. Review `LICENSE` and `THIRD_PARTY.md`. GPL-3.0-or-later is the proposed license for code contributed to this candidate, compatible with the shipped MeanShift adaptation. Confirm that the rightsholders of the newly authored integration approve the grant before a public push. Keep unpublished acquisition material and optional local B providers out of the public tree.
3. Verify the candidate using the commands in `VALIDATION.md` and `python -m pip wheel --no-deps ./MorSTORM-dual ./MorSTORM-B --wheel-dir dist`. Review the GitHub CI results after pushing a review branch. The manually triggered build workflow uploads wheels and `SHA256SUMS.txt` as a build artifact.
4. Create the prerelease only after the review branch and artifacts are approved. Use `CHANGELOG.md` for the release notes, and attach the approved wheels and checksums. Describe the optional B provider requirement and the validated MATLAB/Fiji environment.

The workflows request read-only repository permissions. They do not create a GitHub Release or publish to PyPI. GitHub's [repository license guide](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) describes how the repository license is displayed.
