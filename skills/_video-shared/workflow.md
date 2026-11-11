# Shared video workflow

This folder supports the sibling `gameplay-highlights`, `gameplay-trailers`, `game-thumbnails`, `horizontal-to-vertical` and `gameplay-articles` skills. Share all five folders plus `_video-shared` together. It is not itself a discoverable skill. No creator identity, media, credentials or personal machine paths are required in this package. Article users supply a separate site profile; do not package local profiles or article jobs.

## Article handoff

Review & Select feeds articles directly, without video rendering. See [article evidence contract](../gameplay-articles/references/evidence.md) for reusable observations and coverage. `python _video-shared/article_frames.py MANIFEST REQUESTS_JSON --out ARTICLE_JOB/images` extracts native PNGs from the original source and records requested/actual normalized timestamps and source identity. It requires FFmpeg/FFprobe and Pillow, not Shotcut or GPU checks. Accurate frame selection decodes up to the requested time; unchanged requests reuse hash-verified PNGs. Run one extraction process per output folder. Source metadata mismatch or modified existing images stops extraction. Relevance, clarity and claim consistency require visual/editorial review.

## Runtime and scope

Use [structured production checks](review-workflow.md) before substantial production: capture instructions, establish applicable checks and assess capabilities. Set `VIDEO_JOB_STAGE` to the journal stage ID when running with `VIDEO_JOB_RECORD`/`--job-record`; execution events then link to its contract/baseline. Reports consult journal-backed producer checks where registered. Missing optional reviewer availability does not block production; missing required production verification prevents completion. Preserve raw automated validation as evidence, separate from qualitative review.

For production jobs, use [whole-job records, bounded recovery and reviewed improvements](job-workflow.md). The optional `--job-record JOB` global pipeline flag links tool execution to an initialized shared journal; use it before the subcommand. Legacy standalone commands remain supported. Tool success does not mark editorial stages complete. Run `test_job_workflow.py` for journal/recovery/review-gate checks; semantic evaluation uses the separately reviewed quality cases.

Use Python 3.10+, Pillow, FFmpeg/FFprobe, and Shotcut's `melt` for project-render comparisons. Commands below run from the folder containing these skill folders (`skills` in the standalone toolkit root); from the project root prefix the script path with `skills/`. Alternatively use an absolute script path.

Tools resolve through PATH, `VIDEO_FFMPEG`, `VIDEO_FFPROBE`, `VIDEO_MELT`, or the normal Windows Shotcut installation directory. No automatic installs, background watchers, uploads or publishing. `libx264` is the portable default; set `format.encoder` to `h264_nvenc` only when appropriate. NVENC checks also require `nvidia-smi` for driver identity. Source metadata and free space are checked per job; hardware compatibility samples are reused when dependencies match. Environment samples are shared across sibling jobs under their parent's `.video-workflow-cache`, or an explicit `VIDEO_CACHE_DIR`. Keep that generated cache outside a public repository.

Supported: SDR, square-pixel, unrotated sources (primary plus optional source catalog); timestamp-based trims from CFR/VFR input, explicit CFR output without motion interpolation; chronological or explicitly custom montages; selected original audio stream or silence; static crops, synchronized stacked/row panels, optional title/image overlays, labels, progressive reveal blur, multiple sources and requested music mixing. Read [composition](composition.md) only for these optional features. HDR, rotated/anamorphic input, animated crops and general video transitions require additional implementation. Do not silently approximate unsupported requests.

## Commands

```text
python _video-shared/pipeline.py init SOURCE --job JOB
python _video-shared/pipeline.py inspect SOURCE --job JOB --start 0 --end 300 --step 15
python _video-shared/pipeline.py import-legacy OLD_MANIFEST --job NEW_JOB
python _video-shared/pipeline.py trailer MANIFEST --job NEW_JOB --selections SELECTIONS_JSON
python _video-shared/pipeline.py vertical MANIFEST --job NEW_JOB --layouts LAYOUTS_JSON --authorization "User requested portrait output"
python _video-shared/pipeline.py run MANIFEST
python _video-shared/pipeline.py status MANIFEST
```

`init` writes an empty schema-v2 manifest and source probe. Add evidence-based selections before rendering. `inspect` writes timestamped contact sheets and sparse frame-difference signals, with at most 240 samples per invocation; signals do not rank highlights or guarantee coverage. Inspect the images and supplement sparse sampling around short events. For narrow frame extraction use a short range and suitable step.

For a trailer directly from a recording, pass that empty source manifest to `trailer --selections SELECTIONS_JSON --job NEW_JOB`. The derived manifest validates the selected ranges and source before saving; a prior highlight output/export is unnecessary. Original audio is the default for this route. Review audio/ordering and set the requested `target_duration` before rendering.

`run` renders, validates and writes reports. The separate `render`, `validate`, and `report` commands support targeted resume. `status` reads a compact stage summary. Long jobs should be awaited in bounded intervals up to 60 seconds; avoid repetitive directory listings/full logs when status is unchanged. The process emits a final compact JSON summary with subprocess count, cache hits and elapsed time. These metrics are not model-token counts.

`import-legacy` copies source ranges from the earlier clips or source-in/source-out trailer manifests into a NEW job. It never modifies legacy files or imports their validation claims. Review imported audio, frame rate, colour and layouts. Unsupported legacy layouts need manual translation. Existing job-specific scripts are not needed for new jobs.

## Manifest contract

`manifest.json` is the source of truth. `init` supplies `source_identity` (absolute path, byte size, nanosecond mtime); source identity is checked on every render/validation. This is a metadata fingerprint, not a cryptographic hash of the full recording. If source content changes, explicitly reinspect and rebuild the manifest rather than bypassing the mismatch.

```json
{
  "schema_version": 2,
  "source": "absolute/path/to/recording.mp4",
  "source_identity": {"path": "absolute/path/to/recording.mp4", "size": 123, "mtime_ns": 123},
  "format": {"width": 1920, "height": 1080, "fps": "60", "encoder": "libx264"},
  "audio_stream": 1,
  "outputs": [{
    "id": "C01", "kind": "highlight", "audio": "preserve",
    "segments": [{"in": 10, "out": 45, "reason": "Observed event and payoff", "confidence": "high", "evidence": ["analysis/sheet-1.jpg"], "layout": {"type": "full"}}]
  }]
}
```

Times are seconds, inclusive in/exclusive out. Each segment is rounded to the nearest output-frame duration; total duration is the sum of rounded frame counts. Set `target_duration` on an output to enforce a requested duration within one frame. Source FPS is inspected during init; choose an appropriate output rate rather than automatically converting all footage to 60 fps. `audio_stream` uses FFprobe's absolute stream index. `null` selects the first audio stream if present; `audio: silent` explicitly removes audio. A recording without audio remains silent; stream presence does not establish audible content.

Each output owns an ordered list of segments. A trailer has `kind: trailer`, `ordering: chronological` by default. `trailer --selections` consumes a JSON list of segment objects like those above; without it, all existing segments are reused. Trim selections to the requested duration, then set `target_duration`. The command sorts chronology; validation rejects overlap/backtracking. Use `--ordering custom` only on user request. Audio defaults to the first input output's setting; review mixed silent/audible source-job preferences before assembly.

The vertical layouts file maps original output IDs to equally sized lists of layouts, one per segment. Example for one segment: `{"trailer":[{"type":"crop","rect":[656,0,608,1080]}]}`. `vertical` copies timing into a new 1080x1920 job and records authorization. Layouts: `full`; `crop` with `[x,y,width,height]`; or `stack` with `panels`, each containing `rect` and destination `height`. Stacked panels fill the output width and their heights sum to canvas height. Even coordinates/sizes are required; crop/destination aspect must match within 1% for pixel-alignment tolerance. No arbitrary filter strings are executed. Rows allow independently cropped side-by-side panels; see composition.md. Animated crop tracking must not be represented as supported.

## Outputs, safety and resume

Every render gets an output/settings/source/environment revision key. Files live under `renders/ID-KEY/`; lossless FFV1/PCM segment media is cached under `media/`. Sources and approved older revisions are never overwritten. Shared media is reused only with matching SHA-256 records. Modified or unknown existing files are protected; use a new revision/job and investigate rather than deleting approved files.

Writes use temporary files and completed-file records. A job lock prevents simultaneous mutation. After a crash, confirm its recorded PID is no longer active before removing a stale `.pipeline.lock`. Do not automatically remove locks or retry indefinitely. Partial temporary files are not completed outputs. Lossless intermediates can be large: inspect current free space and estimate selected-range storage before a large run; the executable enforces only a minimum 2 GiB headroom. Keep the complete render directory with its segment media when sharing a Shotcut project.

Shotcut projects reference lossless precomposed segment media with relative paths. Timing is editable; crops/panels are baked in and must be changed through the manifest and rerendered. This deliberately avoids claiming unsupported native crop/keyframe equivalence. Final MP4s and Shotcut renders use the same prepared frames, with sampled comparisons to verify agreement.

## Validation and human review

Automated checks cover exact frame count, duration, dimensions, frame rate, expected audio presence, stream-start alignment, decoding, and MLT-rendered start/middle/end frames of every segment. The mean pixel-difference threshold catches gross disagreement but does not prove semantic equivalence. Missing `melt` leaves project agreement unverified. GUI opening/seeking, audio listening/perceptual sync and semantic/full-vertical visual review remain human/agent review obligations; never label them passed from automated stream checks.

Integrity and project agreement have separate dependency keys. A project-only change can reuse export integrity; new media/settings invalidate dependent checks. Missing comparison evidence is regenerated. Reports derive automated results from validation records and mark human checks unverified; record completed visual/listening review separately with evidence tied to the exact output revision. No numerical ranking predicts virality.

## Evaluation

Run `python _video-shared/test_pipeline.py` from a workspace containing a `tmp` folder (the test creates it if needed). Tests generate isolated synthetic recordings and preserve test evidence; they never process or overwrite user recordings. Keep comparable model/settings, source ranges and quality requirements when measuring token savings. Record uncached input, cached input, output tokens, model calls and revisions separately. Runtime cache metrics measure mechanical reuse only.

## Profiles, revisions and retention

Read only an applicable supplied/project creator profile (for example .creator-toolkit/creator-profile.md). Public defaults do not identify a creator or automatically add a title reveal. Record the profile and relevant instruction in the job when it authorises replacements or effects. Keep per-game constraints in the job rather than promoting them to public rules.

For vertical replacement selections, pass --selections with a mapping of output IDs to replacement segment lists and --replacement-authorization with the user/profile basis. Lists must retain each output's frame count and include replacement_reason for every selection, including retained selections. Layouts map the new list. The command records before/after ranges. Check requested coverage, progression and ending manually; equal duration alone is insufficient.

Read [retention](retention.md) before advising cleanup. MP4 playback is independent of project media; an MLT file is not a self-contained archive. Keep sources, selected assets, manifests and dependencies when future re-edits matter. Do not delete files as part of creation or review.

## Reusable job helpers and progress

`python _video-shared/job_helpers.py COMMAND CONFIG.json` reads UTF-8 JSON. Use helpers instead of copying job-specific setup/render boilerplate; keep footage choices and observations in the job.

- `bootstrap`: `journal`, `requirements` (text/source objects), `instructions` (explicit Markdown/TOML paths), `requirements_source`. Creates or safely resumes journal/B1 only. JSON manifests are job data, not instruction baselines. Continue with preflight, contract and stage registration before execution.
- `budget`: `seconds`, rational `fps` (e.g. `60000/1001`), positive scene `weights`. Returns integer frame allocations and actual duration. Review cuts and source availability; allocation does not select footage.
- `preview`: `manifest`, empty `destination`, even `width`. Preserves source crops/timing, scales panel/effect geometry, accounts for final row/column rounding and validates before saving. Very small previews can fail the 1% crop-aspect check; choose a compatible larger size instead of stretching.
- `sheets`: `source`, `job`, `start`, `end`, `step`. Reuses the narrow-range cached inspection/contact-sheet implementation. Samples are not full playback evidence.
- `deliver`: `journal`, `stage`, `contract`, `source` identifying delivery, and `artifacts` with unique `id`/`path`. Validates the whole batch first, resumes partial registration and protects existing identities. It does not mark checks passed.
- `handoff`: `journal`, `stage`. Returns the exact-revision checklist described in review-workflow.md.
- `dimensions`: image `path`, `aspect` such as `16/9`, optional `exact: [1280,720]`, relative `tolerance` (default 0.001). Reports actual dimensions and pass/fail without modifying the image.

Journal-linked commands require `VIDEO_JOB_STAGE` to name a registered stage and contract; missing binding fails before subprocess execution. Standalone inspection remains supported. Long FFmpeg extraction/effect/audio-mix/encoding commands expose `stage`, output/scene, `processed_media_seconds`, `elapsed_seconds` and command state in `status.json` via `-progress`. Times apply to that command, not the whole job; cached stages may be skipped. No ETA is invented. Interrupted/failed commands are marked accordingly. Validation starts in `validate`; only its results establish automated checks. A process killed externally may leave a running snapshot: reconcile before resuming.

For feature-sensitive edits, output `feature_coverage` is a list of records containing `feature`, `origin` (`user_required` or `producer_selected`), `source`, `disposition` (`kept`, `replaced`, `dropped`), `reason`, and current zero-based `segments` for retained coverage. Dropping a user-required feature needs its explicit `user_waiver`. For portrait replacements of a ledger-bearing edit, pass `--coverage` with updated ledgers keyed by original output ID. Every prior feature and its origin/source must remain accounted for. This validates bookkeeping; editorial inspection still establishes whether the footage shows the feature.
