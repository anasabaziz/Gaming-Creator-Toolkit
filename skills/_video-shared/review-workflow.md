# Production checks and requested review

Read for new production jobs and deliverable revisions using gameplay-highlights, gameplay-trailers, horizontal-to-vertical, game-thumbnails or gameplay-articles. Inquiries, planning-only discussions, skill/instruction maintenance, workflow/tool updates and other work do not enter this role-based process; use normal task handling and appropriate checks without requiring production journals, review-choice questions or formal acceptance records. The producer creates/revises the deliverable and performs the applicable production checks. A separate reviewer assesses specified criteria only when asked. The acceptor records explicit user acceptance where required. Production completion, optional review and acceptance are separate records.

## Start and capture

Commands run from the project root; `S` below means `skills/_video-shared` (substitute the full path, not a literal shell variable). Payloads are UTF-8 JSON files. Keep private jobs, instruction snapshots and evidence outside public skill packages. Do not snapshot credentials or environment/configuration dumps.

1. Read status/reconcile for an existing job. New `init` creates schema 2; legacy schema 1 stays readable. Use a new stage/revision with a contract when revising legacy work. Do not migrate unrelated completed jobs or manufacture historical passes.
2. Capture applicable project instructions, skills/shared procedures and local profiles explicitly with `python S/job_state.py baseline JOB --data baseline.json`. Payload: `{"id":"B1","files":["AGENTS.md",".creator-toolkit/creator-profile.md","skills/game-thumbnails/SKILL.md","skills/_video-shared/review-workflow.md"],"requirements_source":"current user request and job requirements"}`. Add all instructions actually governing the task; do not load unrelated skills. The command saves private copies and toolkit identities. Published articles and gameplay observations are reference evidence, not instructions.
3. Assess production capabilities before substantial work. `python S/preflight.py capabilities.json --out JOB/preflight/P1.json`. Example input: `{"tools":[],"capabilities":{"visual":{"status":"available","method":"image tool","notes":"Successfully opened supplied reference","evidence":["JOB/evidence/image-inspection.md"]}},"handoffs":[]}`. This is an attestation backed by an actual interaction, not a fabricated probe. Missing capabilities are unknown/unavailable. Tool discovery cannot prove listening, continuous playback, GUI operation or perception. Recheck at resumption if the session/method changed; register a new preflight and contract when needed.
4. Register the report using `preflight`: `{"id":"P1","path":"JOB/preflight/P1.json"}`. `contract` then establishes the checklist before production. Consult `review_checks.json`; every default check for the kind must be represented, with criteria from the actual request. Custom checks may be added. Default methods/capabilities cannot be weakened by the payload.

## Contract and review payloads

Example thumbnail contract (IDs designate planned outputs, registered once produced):

```json
{"id":"C1","stage":"thumbnail-r1","kind":"thumbnail","baseline":"B1","preflight":"P1","artifacts":["thumbnail-r1"],"checks":[
  {"id":"coverage","criterion":"Requested game and accepted corrections retained","targets":["thumbnail-r1"]},
  {"id":"dimensions","criterion":"Requested aspect ratio and actual dimensions","targets":["thumbnail-r1"]},
  {"id":"visual","criterion":"Applicable text policy, composition, color and game-art fidelity","targets":["thumbnail-r1"]}
]}
```

Ensure preflight covers every used capability (`editorial`, `technical`, `visual` here). For video, register MP4 and project/dependencies; target each check to the appropriate artifact(s). Article package checks target matching Markdown/HTML/SEO and screenshot mapping. Register supporting evidence separately where it must survive resumption. Record requirements before creating the contract: any later requirement-list change makes it stale and requires a new contract.

New video contracts require `artifact_roles`, mapping every planned ID to `video`, `project`, `dependency` or `report`. Include at least one video and project. Every video must be targeted by coverage, technical, visual, audio and playback (framing for vertical); every project by project comparison and project GUI. Dependencies/reports may be supporting artifacts without separate checks. Other packages must target every delivered artifact in at least one applicable check. Classify actual deliverables honestly; supporting roles are not exemptions for an MP4 or project. Existing contracts stay historical; affected revisions use the new applicability rules.

Stage payload: `{"id":"thumbnail-r1","status":"running","contract":"C1","artifacts":["thumbnail-r1"]}`. Use `VIDEO_JOB_STAGE` alongside `VIDEO_JOB_RECORD` for pipeline execution so execution events link to the contract/baseline. The video manifest continues to own render settings; no duplicated rendering instructions are introduced.

Review command: `python S/job_state.py review JOB --data review.json`.

```json
{"id":"R1","contract":"C1","check":"visual","role":"producer","reviewer":"producer session identity","status":"passed","method":"visual_inspection","coverage":"entire final image at native and thumbnail scale","notes":"Specific observed result and limitations","evidence":["JOB/evidence/visual-r1.md"]}
```

The record seals target/evidence hashes and the contract digest. It proves association/integrity, not the truth of the perceptual judgment. Use specific observations, timestamps or sections; a generic 'looks good' is inadequate. Record `failed` or `unverified` honestly. New reviews explicitly `supersedes` the latest review ID for the same contract/check/role. Do not overwrite evidence used by an old review.

Only permitted checks support `not_applicable`, requiring `reason`, `method: exemption` and evidence of applicability. Silence explicitly requested can exempt listening; missing listening capability cannot. A notes-only article may have a documented screenshot exemption only when its agreed scope permits it; otherwise screenshot coverage stays unresolved. Do not remove checks to bypass missing capabilities.

Automated `validation.json` supports technical/project-comparison checks only. A passed `technical` or `project` review includes `validations: ["clip1/validation.json", "clip2/validation.json"]` covering every target in that check; singular `validation` remains supported. Technical targets must be the reports' exports; project targets must be their projects. All reports must pass, and their targets, dependencies and comparison evidence are sealed together. Reviews for the same check/role replace the complete prior result, not individual clips. Sample agreement cannot establish playback, listening or GUI use. Continuous/full-interval checks need the stated coverage. Keep production review limitations explicit.

`stage` with `status: completed` evaluates every required production check (producer evidence or a specific supported human verification report), exact artifacts/evidence, requirements, preflight and baseline. Failure lists outstanding checks; use `awaiting_review` when required verification is missing. A draft can be delivered honestly without calling production complete.

The same evaluator supplies reconciliation, handoffs, acceptance conditions and dashboard conditions, including unresolved blockers and recursively checked stage dependencies. Cycles are refused. A later issue or stale dependency invalidates current verification without erasing the historical completed/delivered/accepted records. Reconciliation reports this; never treat a saved `completed` label alone as current proof.

## Conflicting findings

Keep the latest finding for each role independently. An unavailable/unverified producer capability can be satisfied by a supported human pass; a failure cannot be silently replaced by a later pass from another role. A requested reviewer failure also requires disposition even when optional review was not an acceptance prerequisite. Retraction of a previous human verification remains unresolved until explicitly addressed.

Use `python S/job_state.py resolution JOB --data resolution.json` with `id`, `contract`, `check`, `reviews` (all current role-head review IDs), `decision` (`corrected`, `rebutted`, `out_of_scope`, or `unresolved`), `reason`, `source`, and preserved `evidence` paths. A resolved disposition additionally names `selected_review`, a current passing producer/human-verifier record. Example: `{"id":"D1","contract":"C1","check":"visual","reviews":["R1","H1"],"decision":"rebutted","selected_review":"H1","reason":"Specific evidence resolves the reported defect","source":"producer assessment of findings","evidence":["JOB/evidence/disposition.md"]}`. The disposition seals the exact findings/contract and evidence; changed findings require a new assessment. It does not create a pass, waive a required independent review, or permit scope changes without a revised contract. Correct changed media in a new revision. A same-role replacement still explicitly supersedes its predecessor. Do not launch extra reviewers to settle a disagreement automatically.

## Revisions and resumption

`status` returns a lightweight journal snapshot with `integrity: not_checked`; it does not hash media. Use `reconcile` for a fresh integrity audit; `--full` returns all state. Hashes are reused only within one audit and keyed by file metadata, never carried forward as fresh proof. Review evidence stays associated with the old revision. New contract IDs retain old checklists and reviews. Do not carry passes to changed media automatically. Reuse requires inspecting relevant dependency identities and recording a fresh review with the unchanged evidence, explicit scope and rationale; otherwise recheck. New capability records also require new contracts. No broad rediscovery/rerender merely to adopt this workflow.

Baseline reconciliation reports instruction/tool changes separately from damaged saved snapshots. Retain an old baseline only after assessing impact: `baseline_assessment` payload `{"id":"A1","baseline":"B1","decision":"retain","reason":"Specific impact assessment","source":"applicable instruction/evidence"}`. This seals the exact changes assessed; later changes require reassessment. Damaged snapshots cannot be waived. To adopt changes, capture a new baseline and create a new contract; current user instructions and mandatory restrictions always govern. A hash change alone never orders a rerender.

## Optional reviewer and acceptance

Use the local workflow profile when supplied. When the configured review preference requests an offer, after production completion and delivery ask: **Would you like a subagent review, or is human review sufficient?** Keep artifacts, briefs, requirements and evidence available. Do not delegate a separate production review unless the user requests it. An unanswered question does not reopen production or authorize a subagent.

Record `review_choice`: `{"stage":"thumbnail-r1","contract":"C1","choice":"pending","source":"post-delivery question asked"}`. After an explicit response use `subagent_requested` or `human_sufficient`, with the response as `source`. Neither choice constitutes a review pass or acceptance. A separate reviewer is invoked only for the requested scope; check that reviewer's methods/capabilities then, not as a prerequisite to production. Provide requirements, exact artifacts and neutral criteria without the producer's verdict. The reviewer returns evidence, coverage and findings; the producer records these with `role: reviewer`. Findings do not silently replace producer records. Reviewer instructions are not a read-only OS sandbox; avoid concurrent edits to the reviewed revision and have the producer register findings.

Requested reviewer records also supply `reviewer_type` (`subagent` or `human`, matching the recorded choice) and `preflight` (the registered capability report for that review). A human's actual report/explicit account of the performed method may support the capability declaration; merely choosing human review cannot. Passed reviewer checks require available evidence-backed capability. Failed/unverified reviews can record what could not be checked. If a named custom agent is unavailable, pass its role instructions explicitly to an available delegation tool only after the user's request. Platform-specific reviewer roles are optional conveniences, not proof of reviewer availability. Use the generic brief in `optional/review/reviewer-brief.md` only after a review request.

`acceptance`: `{"stage":"thumbnail-r1","contract":"C1","decision":"accepted","acceptor":"user","source":"explicit user response"}`. `changes_requested` is also supported. Never infer acceptance from silence, choosing human review or a reviewer pass. If the job explicitly requires separate review, put its check IDs in `acceptance_checks`. Acceptance records preserve outstanding conditions; the user's statement does not waive or pass them. Inspect current conditions through reconciliation before claiming verified completion. Leave this list empty/omitted otherwise. Resolve findings against evidence; create a new revision for changes and preserve prior acceptance/history.

## Archives

See [retention](retention.md) for inventory, copy verification and restore evidence. Backup status is separate from production unless archiving is requested. Register inventory/verification reports with `archive`; register actual playback/GUI restore evidence as artifacts and an explicit journal event. A copy hash pass cannot establish restoration or independent storage.

## Delivery, user closure and human verification

Track delivery, required verification, optional review, acceptance and user closure independently. Before handing off incomplete verification, register `delivery` with `stage`, current `contract` and `source` identifying the delivered links/message. Stage artifacts must match that contract and their saved identities. `review_choice`, `acceptance` and `closure` may then attach to that delivered revision while checks remain outstanding. Older completed stages retain compatibility. New contracts do not inherit delivery or acceptance.

`closure` uses `{"stage":"thumbnail-r1","contract":"C1","decision":"closed","acceptor":"user","source":"explicit closure statement"}`. Acceptance and closure seal artifact identities and `outstanding_at_recording`; they do not change production status or create review passes. “Looks good” may be acceptance; “all jobs completed” may close user work. Neither proves listening, playback, GUI inspection or backup. Preserve historical evidence gaps and do not reopen accepted media merely to change bookkeeping.

When perception is unavailable, generate a concise checklist using `job_helpers.py handoff CONFIG.json` with `journal` and `stage`. Present the exact artifacts, outstanding checks, allowed methods and requested coverage once. Record only the human's actual response. Use `role: human_verifier`, `reviewer_type: human`, named `reviewer`, `source` quoting/locating that report, and the usual `contract`, `check`, `method`, `coverage`, `notes`, `evidence`. Save the response as evidence with its provenance; never manufacture an attestation. This route supports visual, coverage, playback, framing, audio and project GUI checks only. It is a verification handoff, not an independent reviewer or a substitute for automated validation.

A human report satisfies only its named check and exact targets. For passing playback, framing and listening, all roles must specify `coverage_scope: entire_artifact` and describe the actual complete coverage; samples remain unverified for full-interval obligations. A later report may supersede a check, with current target/evidence identities. Changed media invalidates the report. Specific human verification can meet a missing producer capability without pretending that the agent acquired it. Producer passes now require an available evidence-backed capability at registration, so diagnose missing capability before attempting to record a pass.

## Spreadsheet human attestations

For a configured local dashboard, follow [dashboard tracking](dashboard-workflow.md). An explicit owner selection of `Passed - all listed checks performed` against the frozen displayed checklist and exact targets is a human report. Preserve the saved workbook and structured attestation; register its named checks through `human_verifier`. Supported human methods include editorial, visual, metadata, package, continuous playback, full-interval framing, listening and project GUI inspection. Automated validation/comparison remain excluded. Record only the attested method, coverage and criterion; do not fabricate observational prose. Generic acceptance and a choice of human review remain insufficient.

The spreadsheet route supplements the report route above. It can cover article claims/package/screenshots/SEO and custom checks with supported human methods. Production stage gates, stale revisions, full coverage and evidence integrity remain enforced. Explicit acceptance cells are user decisions; pending or changes requested never silently create a pass.
