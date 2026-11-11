# First public release

The project is a release candidate until the required compatibility checks pass. Creating the folder, reading platform docs or adding a CI workflow is not evidence that all platforms work.

## Manual upload of this folder

The prepared `gaming-creator-toolkit/` folder is the upload source for [anasabaziz](https://github.com/anasabaziz). Upload its contents at the GitHub repository root, including `.github/` and `.gitignore`, with the existing directory structure intact. No ZIP or `dist/` folder is needed. The copyright notice is already finalized.

Before uploading, run `python -B scripts/check_package.py` and confirm the folder contains only files listed in `PACKAGE_FILES.json`. Exclude any subsequently generated Python caches, local profiles, jobs, media or credentials; a manual browser upload does not apply `.gitignore` automatically. Keep the documented candidate status while compatibility checks remain pending.

## Validation and optional ZIP distribution

1. Retain the finalized copyright notice for [anasabaziz](https://github.com/anasabaziz) in `LICENSE`. Creator attribution for this toolkit points to that GitHub profile. Forks retain the original notice; the one-time license-holder setup has already been completed.
2. Complete Windows/macOS/Linux helper and media checks plus live application/onboarding checks in [validation](validation.md). Record dated evidence for each requirement in [validation.json](validation.json). Review rights to any newly added third-party material.
3. Run `python scripts/check_package.py --release`. It checks the allowlist, local links, skill metadata, obvious private-path/credential patterns, license finalization and release-check records. It cannot prove exhaustive secret absence or the truth of test attestations; inspect the selected files.
4. Only if a ZIP is wanted, run `python scripts/package.py --release`. It creates and verifies an allowlisted ZIP in ignored `dist/`. Private profiles, jobs, archives, generated adapters, `.env`, dashboard records and Git history are never selected. `python scripts/package.py` instead creates a clearly named candidate ZIP without claiming all release checks passed. Skip packaging when uploading this prepared folder directly.
5. For first publication, extract only that reviewed package into a new standalone repository with clean history, or initialize this public folder alone. Never copy an enclosing private workspace or its Git history. Stage only reviewed public files; run `python scripts/check_package.py --git` to flag tracked files outside `PACKAGE_FILES.json`, then inspect `git diff --cached`.
6. The owner will manually create and upload the repository under [anasabaziz](https://github.com/anasabaziz). Upload the extracted package contents at the repository root, preserving their folders and including dotfiles such as `.github/` and `.gitignore`. Do not upload the enclosing private workspace. For a candidate package, retain the candidate status and outstanding checks in the documentation. This toolkit's scripts do not publish, configure remotes or upload files.

`PACKAGE_FILES.json` is the public inventory. Adding a file requires deliberately adding its relative path. Updating instructions does not require regenerating this list unless filenames change. Do not add media, generated test evidence, personal profiles or binary dependencies. CI evidence and screenshots of application checks may be linked externally if they contain no private information; never paste personal workspace logs into public validation files.

MIT permits proprietary/commercial reuse and does not require publication of modifications. Its copyright/permission notice still travels with copies or substantial portions. See the [OSI license text](https://opensource.org/license/mit) and [third-party notices](../THIRD_PARTY_NOTICES.md).
