# Developing and updating the toolkit

Keep reusable procedures in `skills/`, creator preferences in private local profiles, and job-specific facts in private journals. Update canonical instructions; regenerate adapters rather than editing them. Examples/tests must be fictional or synthetic and must never load a creator's recordings, profiles or credentials.

```text
python -m pip install -r requirements-dev.txt
python scripts/check_package.py
python -m unittest discover -s tests -v
python -m unittest discover -s optional/dashboard -p test_dashboard.py -v
python -m unittest discover -s skills/_video-shared -p test_*.py -v
python skills/_video-shared/test_article_frames.py
```

The shared media suite requires FFmpeg/FFprobe and MLT. See [dependencies](setup/dependencies.md); do not silently skip required tools when assessing release readiness. Tests use isolated synthetic inputs, including paths with spaces, Unicode and punctuation. Some synthetic render evidence is retained under ignored `tmp/`.

Check behavior, not just wording: onboarding must require real confirmation; changed profiles must be detected; installation must preserve unrelated files; packaging must exclude runtime/private data; dashboard decisions must bind to exact revisions; generated feedback must remain literal text. Preserve existing tests and add cases for concrete changes.

The CI workflow tests the portable helpers on Windows/macOS/Linux and exercises media tooling on Linux/macOS. Required Windows media checks and actual application/GUI/perception checks are recorded separately. Do not convert a skipped or unavailable check into a pass. Read [validation](setup/validation.md) and [release](setup/release.md).

To add a public file, deliberately add its relative path to `PACKAGE_FILES.json`, then rerun packaging checks. That allowlist, not a broad directory copy, defines releases. Inspect both staged Git files and the release ZIP. Retain the original copyright notice when forking. Contributions to toolkit code/instructions use the repository's MIT license; no user media rights are implied.
