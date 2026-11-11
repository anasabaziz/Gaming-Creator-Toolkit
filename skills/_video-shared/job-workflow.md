# Whole-job records, recovery and reviewed improvements

This production journal and role-record workflow applies only to jobs and deliverable revisions using gameplay-highlights, gameplay-trailers, horizontal-to-vertical, game-thumbnails or gameplay-articles. Inquiries, planning-only discussions, skill/instruction maintenance, workflow/tool updates and other work do not require this journal, a post-delivery review-choice question or formal acceptance records. Use normal task handling and appropriate checks for those tasks.

New production jobs use schema 2 and the [structured review workflow](review-workflow.md): instruction baselines, capability preflight, immutable check contracts/reviews, optional review choice, separate acceptance and archive records. Read that guide for payloads. `status` is a lightweight snapshot with integrity explicitly not checked (`--full` for state); use `reconcile` for a fresh integrity audit. Legacy schema 1 jobs remain readable with their historical free-text reviews; use new contracts for affected revisions, without inventing past checks or rerendering to migrate.

Use one journal directory per user request, shared by its requested deliverables. Existing video manifests still own render settings. Do not migrate unrelated jobs or create media during planning-only tasks. For an existing production job, initialize a journal with links to its existing artifacts; do not rerender to adopt this workflow.

Commands below run from the project root; replace paths as needed. Payloads are UTF-8 JSON files.

```text
python skills/_video-shared/job_state.py init JOB --data plan.json
python skills/_video-shared/job_state.py status JOB
python skills/_video-shared/job_state.py reconcile JOB
python skills/_video-shared/job_state.py plan JOB --data plan-update.json
python skills/_video-shared/job_state.py stage JOB --data stage.json
python skills/_video-shared/job_state.py artifact JOB --data artifact.json
python skills/_video-shared/job_state.py event JOB --data feedback.json
python skills/_video-shared/pipeline.py --job-record JOB run VIDEO/manifest.json
python skills/_video-shared/article_frames.py VIDEO/manifest.json requests.json --out ARTICLE/images --job-record JOB
```

## Payloads and ownership

- Plan: `{"requirements":[{"text":"Preserve original audio","source":"user request"}],"decisions":[],"issues":[],"next_action":"Review candidate ranges"}`. Updates replace supplied fields only; merge existing lists before updating. Decisions need rationale and their instruction/evidence source. Issues use `stage`, `blocking`, `resolved`, and a description. Store stage dependencies in its `depends_on` field; check them before starting dependent work.
- Stage: `{"id":"highlights","status":"running","next_action":"Review payoff"}`. Allowed status: pending, running, awaiting_review, blocked, completed. Schema 2 completion requires `artifacts` (registered IDs), a matching `contract` and passing structured producer checks. Legacy schema 1 uses `review` evidence. Completion means the requested scope is satisfied; never use it when required production review is missing. Use awaiting_review instead. Tool-stage success alone does not establish editorial completion. Optional separate reviewer choice and explicit user acceptance do not silently change production status.
- Artifact: `{"id":"trailer-r2","path":"absolute/path/trailer.mp4","revision":"render-key","kind":"video"}`. IDs are immutable. Register manifests, evidence, projects, media dependencies, images and article files that must survive resumption separately. Register the final versions after writing; superseded revisions remain recorded.
- Feedback event: `{"stage":"vertical","observation":"Dialogue disappears at 8 seconds","evidence":["path/to/review"],"revision":"trailer-r2"}`. Event IDs from the journal connect feedback to improvement proposals. Never put credentials, environment dumps, or unrelated private content in payloads or command arguments.

Read status at entry and reconcile on resumption. Reconcile checks registered file hashes and flags interrupted running stages. Inspect tool events and validation sidecars for unregistered outputs; verify and register them before relying on them. Do not infer completion from a started event or a file's existence. `job.json` is a summary; the last state in `events.jsonl` is authoritative if the summary write was interrupted. Never edit either by hand. A malformed/incomplete journal tail stops further writes: preserve it for investigation. Never auto-remove `.job.lock` or `.pipeline.lock`; check the recorded process and whether it is still active before an authorized stale-lock repair.

## Recovery

Use these transitions consistently:

| Condition | Next state/action | Resume condition |
| --- | --- | --- |
| Required verification unavailable or pending | `awaiting_review`; deliver an explicitly incomplete draft/checklist once | Actual verification evidence or an agreed revised scope |
| Execution/input/tool failure | `blocked`; preserve operation ID, error and next action | Diagnose the cause and record `resume_change` describing the changed input, capability or resolved cause and its evidence/source when setting `running` |
| Interrupted operation with uncertain outcome | Reconcile artifacts/events first; use `blocked` until diagnosed | Verified existing result, or a justified retry after diagnosis |
| All applicable checks and dependencies satisfied | `completed`, then delivery and optional review/acceptance records | Revisions create new contracts/artifacts; prior history stays intact |

Journal-linked operation failures record `blocked`; commands require a running stage. A resume explanation is an accountable record, not proof that a fix worked: validate the result. Never repeat an unchanged failing call or poll an unchanged blocked state indefinitely. Continue unaffected independent work, then hand off the precise unresolved condition. Subprocess retry limits below do not authorize unlimited agent-level retries.

`VIDEO_JOB_RECORD` is an alternative to the CLI flag, including for programmatic calls. `VIDEO_COMMAND_TIMEOUT` controls non-probe subprocess timeouts (default 3600 seconds, maximum 86400); probes use 120 seconds. Increase the limit deliberately for known long renders. Python's subprocess timeout stops and waits for the direct child; this toolkit does not launch process-tree supervisors. External wrappers that launch descendants need their own lifecycle handling.

Only safe probes retry recognized transient process errors (EAGAIN, EINTR, ETIMEDOUT), once by default. Nonzero exits, invalid inputs, missing dependencies, changed sources, protected outputs, locks and timeouts stop for diagnosis. Renders and extraction never automatically retry. Resume a failed render/validate/report stage through existing hash-verified caches after resolving its cause; do not discard successful prior work. Inspect optional environment settings before execution. Tool events record arguments and executable hashes; do not pass secrets to these media commands.

Thumbnail generation is external: record brief/reference revisions before the call and resulting artifact identities afterwards. If a response is lost, inspect available results before repeating; do not blindly retry a potentially billed generation. Article drafting and editorial review use explicit stage/feedback events, because they do not pass through Python subprocesses.

### Damaged journals and stale locks

Stop writers and preserve the original folder. For damage confined to the final event, inspect the journal and obtain authorization for that concrete repair. Run `python S/journal_recovery.py OLD_JOB --destination NEW_JOURNAL --expected-sha256 SHA256 --authorization "explicit repair authorization source"`. Compute SHA-256 from the diagnosed `events.jsonl`. The destination must be new and outside OLD_JOB. The helper preserves the full original bytes, retains only validated complete sequential events, records the recovery, and marks interrupted running stages blocked. Interior damage or absence of a usable state requires manual investigation. This is journal recovery, not a media copy: preserve original instruction snapshots, artifacts and evidence at their referenced paths. Reconcile the new journal, explicitly use its path for subsequent work and tracking, and retain the old folder as recovery evidence. Do not discover both as competing active journals; configure tracking or exclude the original journal's path before refresh.

For a stale `.job.lock` or `.pipeline.lock`, inspect its PID and the process's identity/start time and command context to rule out both active work and PID reuse. If inactivity cannot be established, stop. With explicit repair authorization, preserve the lock bytes and process-check evidence outside the job, then remove only that exact lock using the native shell and a verified literal path. Record the repair in the journal after unlocking, reconcile, and resume only after diagnosis. No helper automatically removes locks. Never hand-edit event history or discard the damaged original.

## Optional quality cases and improvement review

The proposal/evaluation/decision procedure below is optional for skill and tool maintenance; use it when the user requests that procedure. It is not a required approval gate for ordinary authorized maintenance and does not activate the production roles or post-delivery review offer. Appropriate validation remains required.

Use relevant scenarios in `quality_cases.json` for synthetic regression checks. Give the relevant request and fixture to the skill under review, save its response, and assess every criterion in order. These cases test decisions, not real video/image perception. For a visual correction, additionally retain a representative private media fixture and exact artifact revision, inspect it, and save review evidence. Do not claim a synthetic case establishes continuous playback or style fidelity. Keep private fixtures, profiles, jobs and generated evaluations outside public skill distributions.

Propose the narrowest change: job-only fact, creator/site preference, general skill rule, or tool defect. No automatic skill rewriting or scheduled learning occurs.

```text
python skills/_video-shared/job_state.py propose JOB --data proposal.json
python skills/_video-shared/quality.py JOB PROPOSAL_ID reviews.json --out evaluation.json
python skills/_video-shared/job_state.py decide JOB --data decision.json
```

Proposal payload: `{"id":"P01","failure_events":["existing-event-id"],"target":"path/to/SKILL.md","rationale":"Why this is generalizable","change":{"before":"exact old text","after":"exact proposed text"},"cases":["vertical-hud"]}`. Include risks/tradeoffs as additional fields. The original target hash is saved. Test the proposed change in an isolated candidate copy and retain that copy and its test response as evaluation evidence, without replacing the live skill first.

Reviews payload is a list: `[{"id":"vertical-hud","status":"passed","criteria":["passed","passed","passed"],"reviewer":"identified human or agent","notes":"Specific observed behavior and limitations","evidence":["candidate-copy.md","response.md","review.md"]}]`. Record failed/unverified criteria honestly. The evaluator seals references/hashes and validates completeness; it does not independently judge prose or pixels. Extend the case catalog when a new failure needs a distinct scenario, then test it. Run applicable mechanical tests for tool changes as well.

Decision payload: `{"id":"P01","decision":"accepted","reviewer":"reviewer identity","reason":"Evidence and tradeoffs","evaluation":"evaluation.json"}`; rejection needs no passing evaluation. Acceptance requires all proposal cases passed and unchanged target/evidence. Acceptance records a decision only: it never edits the target. Apply a reviewed change only within an authorized change task; record the resulting revision and validation afterwards as an event. Rejected or revised proposals use new IDs. Stored feedback does not train the underlying model.

## Configured dashboards

Follow [dashboard tracking](dashboard-workflow.md) when a local profile configures it. Refresh retained metadata before delivery and consume saved human decisions at resumption. A durable dashboard index preserves historical job summaries independently of removable job directories; it does not replace production journals or media backups.
