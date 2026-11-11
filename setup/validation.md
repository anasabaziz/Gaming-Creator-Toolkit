# Compatibility and validation

Release targets are Windows, macOS and Linux, with Codex, Claude Code and Grok setup paths. This candidate must not be advertised as fully tested across all targets until the [release check records](validation.json) contain actual passing evidence.

## Mechanical checks

Run the commands in [CONTRIBUTING](../CONTRIBUTING.md). Package tests exercise safe installation/updating, explicit profile confirmation, profile change detection, public ZIP contents and dashboard workbook round-trips. Shared tests cover synthetic video rendering, project comparisons, screenshot extraction, journals, recovery and exact-revision verification. These are technical tests, not real gameplay editorial or perceptual evaluation.

CI defines Windows/macOS/Linux helper/dashboard jobs and Linux/macOS media jobs. Windows media tests use the installed Shotcut distribution locally. A defined workflow is unexecuted until a run succeeds. No external CI was triggered while assembling this candidate.

## Application checks before release

For each supported agent, start a fresh standalone project with no personal profiles. Confirm all five skills are discoverable/registered, direct invocation asks for customization, profiles are saved only after confirmation, a restart reuses them, and a changed profile requires reconfirmation. Confirm available tools and a representative workflow; record missing image/playback/listening capabilities honestly. Grok import and shared-resource access need explicit testing.

On each OS, test a synthetic export and a Shotcut project open/seek, retain its dependencies, and verify portrait framing/audio using actual playback/listening. Automated frame comparisons do not satisfy these checks.

For Excel and LibreOffice, open a synthetic dashboard, read the checklist, edit a pending review/acceptance, save and close, refresh, and confirm decisions preserve exact revision identity. Also test sorting and literal feedback beginning with `=`. Never use a real creator's review decisions as test data.

## Current assembly results

Verified locally on Windows on 2026-11-10 using Python 3.12.10, FFmpeg/FFprobe n9.0.2-12 and MLT 7.41.0 from the installed Shotcut distribution:

| Check | Result |
| --- | --- |
| Setup, installation, privacy packaging and workbook integration | 12 tests passed |
| Dashboard decision/journal regression suite | 18 tests passed |
| Shared workflow, media rendering, project comparison and recovery suite | 56 tests passed |
| Standalone article-frame extraction/protection check | Passed |
| Skill-creator validator | All five skills passed |
| Public file inventory, internal links and metadata audit | 87 files passed |
| Python syntax and CI YAML parse | Passed |

The 86 unit/integration tests include a synthetic end-to-end dashboard generate/edit/save/refresh cycle with idempotent decision import. This verifies workbook structures and Python behavior, not Excel/LibreOffice GUI compatibility. All media inputs were synthetic; no creator recording or personal profile was processed. Public evidence is summarized here without machine-specific paths or private logs.

No macOS/Linux runners, live Codex/Claude Code/Grok installation session, Shotcut GUI/full-output perceptual review, or Excel/LibreOffice GUI round-trip was performed in this assembly. These release checks remain pending. The CI workflow has been parsed but has not run on GitHub.

On 2026-11-11, the owner supplied [anasabaziz](https://github.com/anasabaziz) as the toolkit creator profile. The copyright notice and publication documentation now use that identity. This documentation update does not change the compatibility results above.
