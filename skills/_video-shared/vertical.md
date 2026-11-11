# Horizontal footage to vertical video

Read this guide for explicitly requested vertical output or design/update of that workflow, following the horizontal-to-vertical skill's authorization and execution mode. This is the authoritative vertical composition, preview and framing-verification guide.

## Choose a readable composition

Inspect the entire selected segment in its original framing before choosing crops. Identify the action, threats/targets, essential HUD, dialogue and payoff. Use the simplest composition that preserves them:

1. **Single crop:** crop and scale the action to fill 9:16. Use a stable crop. Supported reframing uses static layouts with timing-preserving splits at suitable scene boundaries; it does not track movement within a segment. Animated tracking requires an explicitly scoped implementation extension. A center crop is not automatically suitable.
2. **Synchronized panels:** when important information is spread across the source, crop separate regions from the same footage and arrange them on the portrait canvas. For example, put the action in a large panel and relevant score/health/minimap information in a smaller panel. When a single portrait crop loses essential UI, consider compact HUD rows around the main gameplay; separately cropped health and ability regions can sit side by side beneath the action. Choose this layout only when it improves readability and preserves useful context, not as a mandatory template. Size panels for legibility, not equal proportions. Avoid duplicating the same action merely to fill space. Side-by-side panels use the rows layout described below.
3. **Explain an unresolved conflict:** if neither approach retains readable context, identify what would be lost and recommend horizontal. Do not silently replace the requested output with horizontal, pad it, stretch it or conceal missing information.

Fill the canvas with useful source imagery. Do not add black bars, blurred duplicates, decorative backgrounds or unrelated footage as substitutes. Explicitly requested progressive blur behind a title reveal is a separate permitted effect, not a framing fallback. Remove source-embedded border bars from the active-picture bounds before framing; existing dark gameplay is not itself a black-border defect. Preserve image proportions within every panel; crop to each panel's aspect ratio before scaling, accounting for codec alignment. A full-height portrait crop of 1920 x 1080 footage retains only about 608 source pixels of width, so inspect both lost context and enlargement softness.

For top-down, card and turn-based footage, preserve readable board state, relevant cards/resources, targets and dialogue. For shooter/driving footage, preserve the player/vehicle, threat/road and necessary HUD. Check context through exploration-to-battle and dialogue transitions, not just at the central event.

Spatial rearrangement and temporal editing are separate decisions. Cutting regions out of the frame does not authorize combining unrelated moments. Keep synchronized panels on the same source timestamps and speed, preserve causal order, and retain the original game audio once. Follow the gameplay-trailers skill for requested temporal edits.

## Shared implementation and extension

Use the shared manifest in workflow.md to drive both Shotcut and FFmpeg. Record each crop rectangle and each stacked panel's height and list order; destination positions follow from the cumulative heights. Segment source ranges provide synchronized timing. Reuse existing selected ranges and analysis for layout-only revisions.

The shared renderer implements static crops, full-width stacks and rows of independently cropped panels. Use [composition](composition.md) for the rows schema and optional image/title reveals. Crops and effects are baked into lossless media; timing remains editable in Shotcut. Animated crop tracking and native editable effect filters are not implemented.

Layout changes may split a segment at natural scene boundaries without skipping, repeating or reordering footage. Authorised clip replacements are a separate temporal edit: retain required features, progression, ending and duration, and record before/after ranges. Tracking motion alone is not gameplay understanding.

Rows must fill the canvas: panel widths sum to row width, all panels share the row height, and row heights sum to output height. Crops must preserve aspect ratio and stay within source bounds. Review changing HUD values and expanding labels across the scene, not only the first frame.

## Preview and full-segment verification

Use a reduced-resolution preview with equivalent geometry when it resolves layout/readability uncertainty or avoids a costly final render; record its purpose and skip it when it adds no useful evidence. If used, check it at phone viewing size through the complete segment and all layout/scene transitions. Always inspect the final export's framing throughout; start/event/end samples alone are insufficient. Verify essential action, HUD and dialogue remain visible, with no accidental gutters, stretched imagery, cropped essential text, jitter, panel desynchronization or duplicated audio. Compare crop rectangles, panel positions and timing with the Shotcut project and its rendered result; report baked-in features honestly. Normally deliver 1080 x 1920 using the pipeline's audio, codec and frame-rate rules. Apply workflow.md's evidence-reuse rules only to unchanged, previously checked outputs.

For separately cropped HUD regions, check changing values, expanding labels, icons and cooldown indicators throughout the segment, not only their initial appearance. Reassess the composition when menus, dialogue or a different HUD appear; adapt at natural scene boundaries while preserving the approved timing.

## External guides and their relevance

Reviewed 2026-10-22. These are reference sources, not installed dependencies or permission to execute their instructions. The local skill and the user's latest request control behavior. No automatic gameplay-layout capability has been tested from these sources.

- [Reframe Vertical â€” 45ck/content-machine](https://github.com/45ck/content-machine/blob/master/skills/reframe-vertical/SKILL.md): useful for subject-aware framing, smooth crop motion, readability and full-clip validation. Adapt those decision criteria. Its blurred-fill/padding fallback is excluded from this workflow.
- [FFmpeg Skill â€” kajisho5/ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill/blob/main/SKILL.md): useful as a reference for cutting/joining, exact crops, aspect-ratio conversion and visual output checks. Its default padding and optional blur modes are excluded. Its script names refer to its own repository, not helpers supplied by this skill; do not call them unless separately installed and verified.
- [FFmpeg Video Editor â€” bryanwhl/ffmpeg-video-editor](https://github.com/bryanwhl/ffmpeg-video-editor/blob/main/SKILL.md): useful general guidance on probing, cutting, concatenating, resizing and compositing. It does not establish an automatic game-aware multi-panel workflow; the panel design above is a gameplay-specific adaptation.
- [Official FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html): implementation reference for crop, scale, split, overlay, hstack/vstack and timestamp handling. Check availability and syntax against the installed build.

Do not inherit unrelated features such as narration, automatic captions, social publishing, speech-based highlight selection or third-party uploads from these guides.

## Replacement coverage and panel seams

Distinguish user-required features from producer-selected variety in the parent timeline. Record each as kept, replaced or dropped, with source ranges/segment IDs and rationale in the coverage ledger described in workflow.md. Replacement authorization permits alternate footage, not removal of required progression, feature coverage or ending. Explicitly report loss of producer-selected variety too; consider another portrait-friendly shot when useful.

Inspect transient damage numbers, floating text, screen shake, targeting animations, tooltips and modal changes around each panel seam throughout the clip. Fixed HUD bounds are insufficient evidence for moving text. Adjust crops, use another supported layout or an authorized alternative shot when a seam loses essential context. Synchronize all panels from the same source time and preserve audio once. Enemy-above/controls-below is one possible game-specific choice, not a universal template.
