# Optional composition

Use this reference for titles, labels, row panels, roundups and requested music. These are optional capabilities, not automatic public defaults. All assets must be supplied/selected for the task. Existing schema-v2 jobs remain valid.

## Source catalog and ordering

The primary `source`, `source_identity` and `audio_stream` remain unchanged and have the reserved source ID `default`. Optional `sources` maps IDs to `{path, identity, audio_stream}`. `identity` is `pipeline.fingerprint(path)`; record it when inspecting the source, never fabricate it. Segments choose `source_id`, defaulting to `default`. Times are relative to that recording. Demo/build/session metadata belongs in the job/evidence and does not affect rendering.

Multiple-source outputs require `ordering: custom` and `ordering_authorization` describing the user's requested/approved storyboard. Never sort different recordings by their unrelated local timestamps. Single-recording chronology remains the default. Use `trailer --ordering custom --ordering-authorization "Approved storyboard"` when deriving a roundup from a populated source catalog. Source ranges may reuse earlier inspected recordings without re-exporting highlights.

Before rendering, check a requirements table against source ranges: features/modes, exclusions, progression, opening/ending, duration, audio and labels. Changing a requirement invalidates its editorial check. Render validation cannot establish semantic coverage.

## Static row panels

Each row spans the canvas. Panel widths must sum to canvas width; row heights sum to canvas height. Coordinates, sizes and destinations must be positive/even where applicable, within source bounds, and preserve crop aspect ratios within 1%.

Example for a 180 × 320 preview from 320 × 180 footage:

```json
{"type":"rows","rows":[
  {"height":180,"panels":[{"rect":[0,0,180,180],"width":180}]},
  {"height":140,"panels":[{"rect":[0,0,90,140],"width":90},{"rect":[230,0,90,140],"width":90}]}
]}
```

Choose actual crops through review; this is schema illustration, not a universal HUD layout. All panels use the same source time and original audio once.

## Image reveals and labels

An optional segment `effects` list contains image effects. All times are relative to the segment, start inclusive/end exclusive. Dimensions and positions use output pixels. Example:

```json
{"kind":"image","path":"/absolute/path/title.png","identity":{},
 "start":3,"end":8,"x":108,"y":700,"width":864,"height":432,
 "fade_in":1,"move_y":120,"blur_sigma":18,"blur_ramp":2}
```

Replace the example identity with `pipeline.fingerprint(path, True)`, including SHA-256. Artwork is fitted proportionally inside the specified box, with transparent unused space. Set x/y to `(canvas-box)/2` for centring. Positive move_y approaches the final position from below; fade_in controls fade and movement duration (movement alone defaults to 0.5 seconds). The title remains sharp. Background blur progressively blends clear footage into a Gaussian-blurred copy over blur_ramp seconds, then remains blurred until effect end. It is not an animated crop or a blurred portrait filler. Do not overlap multiple blur effects unless deliberately reviewed.

Labels use an output-level `label_style` with x, y, width, height and font_size, optionally font/font_identity, color and background. A segment uses `label: {"text":"Game Name"}`; default timing covers its entire duration. Optional start/end override timing. A missing label means intentionally label-free; record those intervals in the storyboard. A font file requires its full fingerprint. Without a font, Pillow's bundled font is used; multilingual text should use a supplied suitable font and be visually checked. Labels are rasterised as literal text, not interpolated into filter expressions. Oversized text is rejected instead of clipped.

Example at 1920 × 1080:

```json
{"label_style":{"x":64,"y":824,"width":900,"height":100,"font_size":48},
 "segments":[{"in":10,"out":18,"label":{"text":"Example Game"}}]}
```

Inspect each label at its first visible frame, middle and last visible frame; check neighbouring label-free intervals. Reveal samples also include fade completion and boundaries. The renderer writes `effects-review.json` and adds these sample frames to MLT/export comparisons. This establishes sample agreement, not correct spelling, readability or proof that an intended label was specified. Compare the label inventory with the storyboard and inspect images.

For a roundup, record output `label_requirements` as one text string or null per segment, copied from the approved storyboard. A string requires that exact label throughout the segment; null requires no label. Validation rejects missing, mistimed or unexpected labels against this list. This catches specification mistakes before rendering; visual checks remain necessary for readable results.

## Audio and music

### Audio joins

For montage cuts, assess discontinuities in ambience/music, clipped effects or speech, abrupt level changes and the opening/ending. Keep a hard cut when it serves the action and sounds clean; do not fade every cut automatically. Use short fades for clicks or abrupt tails, and an audio overlap/J-cut/L-cut when continuity needs it and suitable source handles exist. Paired fade-out/fade-in creates a dip; it is not an overlapping crossfade. Choose timing by listening, preserving important impacts, dialogue and sync. Do not move approved picture cuts or shorten the trailer merely to accommodate a crossfade.

Record output join time, source handles when used, treatment, duration and reason in the edit plan. Preserve original game audio by default; smoothing joins does not authorize added music. If listening is unavailable, record provisional treatments and hand off the exact joins with the complete-output listening check; stream presence or waveform measurements cannot establish that a transition sounds good.

The current shared renderer exposes segment gain and music mixing, but no declarative fade, crossfade or J/L-cut fields. Do not add invented manifest keys or assume concatenation smooths sound. Use a supported editing path or implement and test the needed renderer support within the authorized task. Retain reproducible settings and audio dependencies. A custom audio repair must update the delivered Shotcut project as well as the MP4; validate the actual revised export/project, including duration, sync and join regions. Earlier validation of the pre-repair render does not cover the repair. Declare unsupported validation as outstanding.

### Music mixing

Original audio remains the default. `audio: silent` forbids music. Per-segment `audio_gain` defaults to 1; use 0 to mute selected game sound. Missing audio sources receive silence only when the output requires an audio stream. Optional output `music` contains path, full identity, authorization, credit, optional audio_stream (absolute index), offset (seconds), gain (default 0.25) and loop (default false). Music must cover the timeline unless looping is explicitly selected. Obtain/verify licensing for the intended use when selecting the track; a credit string is a record, not legal verification.

Mixing uses the continuous output timeline, not a restart at each cut. Game and music gains are literal; there is no automatic ducking, normalization or clipping guarantee. Listen to the mix and check levels before delivery. `MUSIC-CREDIT.txt` is delivered with the render. No music lookup, download or publication is performed by the renderer.

## Revisions and editability

The toolkit caches trimmed/framed media, then effects, then audio mixing independently. Swapping artwork preserves the underlying clip and unchanged scenes. Changes to music, timeline offsets or sound gains invalidate affected audio mixes. Fonts/art/music have content hashes; sources use metadata identities. Review a changed asset, then update its identity explicitly.

Shotcut references lossless prepared segments with editable timing. Crops, labels, reveal motion/blur and mixes are baked in. Revise settings and rerender for these changes. This minimizes repetitive implementation work; it is an engineering choice, not a measured guarantee of lower model-token usage. Native effect filters can be considered if a future repeated-edit comparison demonstrates less total work.

Keep sampled visual inspection, continuous playback, perceptual audio listening and GUI opening/seeking as distinct review records tied to the exact revision. Never claim full playback from sample sheets. Preserve source media, the manifest, supplied artwork/fonts/music and toolkit for reproducible re-edits; preserve the complete render folder for timing edits.

Reveal blur uses timed blur, expression blending only during the ramp, and the fully blurred branch during the hold. Overlay artwork stays sharp and audio is copied. Pipeline version changes invalidate render caches for future builds; do not rerender accepted work simply to adopt the optimization. Benchmark changes on synthetic sources and compare decoded frame/audio data, including effect start/end and last frame, before claiming performance improvements.
