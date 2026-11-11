# Release readiness and repository updates

The source repository is [Gaming Creator Toolkit](https://github.com/anasabaziz/Gaming-Creator-Toolkit). The initial upload is complete. The project remains a release candidate until the required compatibility checks pass; publication alone is not evidence that all platforms work.

## Updating the public repository

Keep updates within this standalone repository. Never copy an enclosing private workspace or its Git history. Retain the finalized copyright notice in `LICENSE`; forks must preserve the original notice.

`PACKAGE_FILES.json` is the public inventory. Add or remove entries deliberately when public filenames change. Keep `.gitattributes`, `.github/` and `.gitignore` in the inventory. Do not add media, generated test evidence, personal profiles, credentials, dashboard state or binary dependencies.

Before committing:

1. Run the applicable checks in [CONTRIBUTING](../CONTRIBUTING.md) and `python -B scripts/check_package.py`.
2. Stage only reviewed public changes, including intended deletions. Run `python -B scripts/check_package.py --git` after staging to flag tracked files outside the inventory.
3. Inspect `git diff --cached` and `git status --short`. Git ignore rules do not remove already tracked files. A manual browser upload does not apply `.gitignore`; select only the public inventory if using that route.
4. Keep candidate status and outstanding checks accurate. These scripts do not publish, configure remotes or upload files.

## Validation and optional ZIP distribution

1. Complete Windows/macOS/Linux helper and media checks plus live application/onboarding checks in [validation](validation.md). Record dated evidence for each requirement in [validation.json](validation.json). Review rights to newly added third-party material.
2. Run `python scripts/check_package.py --release`. It checks the inventory, local links, skill metadata, obvious private-path/credential patterns, license finalization and release-check records. It cannot prove exhaustive secret absence or the truth of test attestations; inspect the selected files.
3. If a ZIP is wanted, run `python scripts/package.py --release`. It creates and verifies an allowlisted ZIP in ignored `dist/`. Private profiles, jobs, archives, generated adapters, `.env`, dashboard records and Git history are never selected. `python scripts/package.py` instead creates a clearly named candidate ZIP without claiming all release checks passed. A ZIP is not required for repository updates.

CI evidence and screenshots of application checks may be linked externally if they contain no private information; never paste personal workspace logs into public validation files.

MIT permits proprietary/commercial reuse and does not require publication of modifications. Its copyright/permission notice still travels with copies or substantial portions. See the [third-party notices](../THIRD_PARTY_NOTICES.md).
