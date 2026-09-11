# QC taste update protocol

Use this only when updating or auditing the profile.

## 0. Compute the incremental scope, and be willing to stop

An update reads **only what has been added since the last update**, and an update that finds
nothing taste-bearing is a correct update.

Run:

```bash
python tools/taste_scan.py
```

It compares `ResearchAssets/ai-chat-history/*.md` against `consumed_records` in
`taste-rules.yaml` and reports each record as:

- **new** — never mined; read all of it;
- **changed** — mined before, but the file's sha256 differs; read from the recorded line
  count onward. Sessions are re-exported as they grow, so this is the normal case for an
  ongoing session;
- otherwise skipped.

Do not re-read a record that is already consumed. Do not use a date as the cursor: the
cursor is per file for a reason. `evidence_through` was already 2026-09-09 when a
2026-09-07 methodology session was exported for the first time; a date cursor would have
placed it permanently out of scope.

**Stopping is a valid outcome, at two points:**

1. `taste_scan.py` reports nothing in scope → report "no new records" and stop. Change nothing.
2. Records are in scope but none of them contain a human decision that bears on creative
   taste — an engineering session, a deployment, a bug hunt, pure repository administration →
   report which records were read and why nothing qualified, then advance the cursor only
   (see step 5b). Do not manufacture a rule to justify the run.

Neither outcome is a failure, and neither needs QC's approval, because neither changes a
rule. Only rule changes need approval.

## 1. Collect eligible evidence

Within the scope from step 0, extract only human-authored or human-labeled events:

- `seed`: QC introduces a creative fact or direction;
- `selected`: QC chooses among alternatives;
- `rejected`: QC explicitly refuses an option or property;
- `revised`: QC specifies how an existing result must change;
- `overrode`: QC replaces an AI default with a durable rule;
- `approved`: QC explicitly accepts a proposal or result;
- `stopped`: QC decides further change is unnecessary.

Do not treat silence, continuation to a new topic, or an AI claim that the user was satisfied as evidence.

## 2. Separate scope

Classify every candidate as one of:

- `global`: potentially transferable beyond this project;
- `qc-kindergarten`: creative selection logic for this world;
- `character`, `episode`, or `visual`: narrower creative scope;
- `canon`: route to bibles or stories, not this skill;
- `workflow`: route to the relevant production skill unless it changes creative selection itself;
- `one-off`: keep only with the task; do not update the profile.

## 3. Compare with canonical rules

For each candidate, choose one operation:

- `add`: genuinely new rule;
- `strengthen`: new independent evidence supports an existing rule;
- `weaken`: a counterexample narrows or lowers confidence;
- `revise`: the rule's wording or scope is wrong;
- `retire`: QC explicitly reverses it or evidence no longer supports it;
- `no-change`: the event is already covered or too local.

One event normally creates a `provisional` rule. Repetition across independent tasks may become `repeated`. Use `stable` only for an explicit durable instruction or a pattern supported across sessions and artifacts. Confidence is about evidence strength, not importance.

## 4. Present a candidate diff

Before editing canonical files, show QC:

```markdown
## QC Taste 候选更新

### 新增 / 增强 / 削弱 / 冲突
- Rule ID：
- 当前规则：
- 建议变化：
- 适用范围：
- 新证据：来源、回合、人类决定摘要
- 反例或不确定性：
- 建议置信度：
```

Ask QC to approve all, approve selected rule IDs, revise, or reject. Questions and comments are not approval.

## 5. Apply an approved update

Update all affected artifacts in one pass:

1. `references/taste-rules.yaml` for canonical structured state;
2. the domain files under `references/taste/` only when application behavior changes — in both languages, then `python tools/taste_sync.py stamp <part>`. The rule's scope decides the file: `story`, `character`, `prose`, `continuity` → `story`; `visual` → `image`; `story_visual` → `story`, and check `image`; `revision` or anything true of every domain → `_shared`; storyboard and video scopes → `storyboard` and `video`;
3. `references/evidence-index.md` for new provenance and counterexamples;
4. version and `evidence_through` fields;
5. `consumed_records` — for every record read in this run, write its current path, sha256
   and line count. Compute them the same way `tools/taste_scan.py` does.

### 5b. A run that changes no rule

When step 0 ended at one of its two stopping points, or when every candidate resolved to
`no-change`, update `consumed_records` and nothing else. Record the outcome as a line in
the scan log at the bottom of `references/evidence-index.md`: date, records read, and one
sentence on why nothing qualified. Leave the version, `evidence_through` and every rule
untouched.

This bookkeeping is not a rule change and does not need approval — but the report to QC
still happens, so a silent no-op is never how QC learns an update ran.

Use semantic versions loosely: patch for evidence/confidence only, minor for behavior-changing rules, major for a new model of taste. Preserve retired rules and their reason in the evidence index rather than erasing history.

## 6. Check for drift

Before finishing:

- confirm every rule has evidence;
- confirm every evidence ID resolves;
- ensure AI-only suggestions did not enter the profile;
- ensure canon and temporary constraints were not generalized;
- compare the new profile against at least one older accepted work and one recent decision;
- report unresolved conflicts rather than averaging them away.

Periodic automation may perform steps 0–4 and remain quiet when no meaningful candidate exists. It must not perform step 5 without explicit QC approval; it may perform step 5b, since that advances the cursor without touching a rule.
