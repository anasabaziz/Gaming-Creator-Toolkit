# Review handoff and screenshot workflow

Read `../../_video-shared/workflow.md` for source identity, inspect commands and sampling limitations. Reuse its schema-v2 manifest and existing evidence. Do not require new video renders, NVENC tests or Shotcut checks for an article.

Review & Select can write `review-evidence.json` alongside the manifest. Minimal contract:

```json
{"schema_version":1,"source_identity":{"path":"recording.mp4","size":123,"mtime_ns":123},"observations":[{"id":"E01","in":10,"out":45,"observation":"Visible event, without inferred intent","confidence":"high","uncertainty":"","frames":[{"time":24.5,"path":"analysis/frame.png"}]}],"coverage":[{"in":10,"out":45,"method":"sequence review"}],"limitations":["Other ranges were not reviewed"]}
```

Use the actual manifest identity, not these example values. Existing jobs without this sidecar remain usable: create concise observations only after viewing their evidence. Filenames, selection scores and automated reports do not prove semantic claims. Distinguish sparse samples from continuously watched intervals. Save observations useful to articles even when they are not exciting enough for highlight selection.

Map claims to supported, potentially conflicting, not covered, personal account, or external fact. Cite observation IDs/timestamps in the private report. Lack of footage support is not contradiction. A single frame cannot establish game-wide performance, playtime, causality or general mechanics. For potential conflicts include the user's wording, visible evidence, why it may differ and the unresolved question. The user resolves these manually; no need to halt unaffected work.

For each eligible H2, select a relevant clear moment from reviewed frames. If missing, search a bounded relevant interval in the same recording using `inspect`, then expand to another likely interval only when useful. Stop and ask when no appropriate frame can be found; record ranges inspected. Do not force screenshot selection from action highlights for a quiet UI/strategy section.

Write `screenshots.json` as a JSON list of entries:

```json
[{"section_id":"section-1","heading":"Combat","time":24.5,"alt":"Tank approaching a large enemy vehicle","caption":"","evidence_ids":["E01"]}]
```

Extract native frames with:

```text
python skills/_video-shared/article_frames.py MANIFEST screenshots.json --out ARTICLE_JOB/images
```

Requests use seconds in the original source, not trailer timeline time. The helper checks source identity and returns actual selected frame timestamps in a provenance record. Inspect final PNGs: no blur/obstruction, misleading crop or incorrect alt text. Use the original frame/HUD; no generative changes. Reuse unchanged files only when their hashes match. New selections create new filenames. Reusing one image across sections should be avoided when a distinct relevant frame is available.

Pros/Cons and Final Verdict equivalents are exempt. Record exemptions by section ID in the editorial report rather than relying on a literal English heading match. Image choice remains editorial judgement; automated extraction cannot establish relevance.

For multiple recordings, the manifest may include the sources catalog described in [composition](../../_video-shared/composition.md). Add source_id to each observation, coverage interval and screenshot request (default means the primary recording). Screenshot times always refer to that original source. Record game, demo/build and session context when known; unknown metadata stays unknown. The extractor supports source_id without invoking video rendering.
