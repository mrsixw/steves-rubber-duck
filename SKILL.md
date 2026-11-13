---
name: steves-rubber-duck
description: Obtain a read-only second opinion from a separate capable AI model on implementation plans, completed code changes, and text about to be published as the user. Use automatically before presenting or implementing a substantial plan, before declaring a change complete, and before publishing a PR description, comment, or ticket update; use explicitly when asked to rubber-duck, critique, review, or get a second opinion. Never invoke from an existing RUBBER_DUCK_CHILD review.
---

# Steve's Rubber Duck 🦆

Use the bundled router to ask a separate model family to critique a plan or
change. Treat the duck as a read-only Cardboard Engineer: it finds substantive
problems, while the primary agent owns every final decision. 📦👷🦆

## Guard against recursion

If `RUBBER_DUCK_CHILD=1` is present in the environment or review prompt, do not
invoke this skill or another AI. Return the requested critique directly.

## Choose the checkpoint

- Review a non-trivial plan after it is complete and before presenting or
  implementing it. Use the explicit plan text, not hidden reasoning.
- Review the final scoped diff after validation and before declaring code work
  complete.
- Review text you are about to publish as the user (PR description, PR or
  issue comment, Jira or Confluence update) before posting it, because a
  published mistake is hard to retract. Use `--kind code` with the drafted text, the diff
  or facts it describes, and any existing published text it changes, and ask
  the duck whether every claim is accurate and current.
- A change looking small, or the user approving the post, is not a reason to
  skip review. Skip automatic review only for simple factual answers that change
  and publish nothing. Honor an explicit review request regardless of size.

Use `--tier auto` by default. It selects a high-capability review for security,
production infrastructure, destructive operations, migrations, concurrency,
public interfaces, architectural changes, or repeated uncertainty.

## Prepare the review packet 📦

Include only:

1. The user's goal and acceptance criteria.
2. Relevant constraints and repository conventions.
3. The proposed plan, or the scoped diff plus validation results.
4. Specific uncertainties the reviewer should challenge.

Do not include credentials, unrelated user changes, hidden chain-of-thought, or
unnecessary repository content.

## Run the router 🦆🔀

Resolve this skill's directory, then pipe the review packet to:

```bash
python3 <skill-dir>/scripts/steves_rubber_duck.py \
  --caller <claude|codex|copilot|agy> \
  --caller-family <anthropic|openai|google|unknown> \
  --kind <plan|code> \
  --tier auto
```

Determine the actual active model family. Copilot and AGY can broker models
from multiple families, so do not infer their family from the CLI name when the
active model is known.

Useful controls:

- `--reviewers <N|all>` asks for a panel of up to N reviewers, one per distinct
  model family other than the caller's (two for a known caller family). The
  default comes from `RUBBER_DUCK_REVIEWERS`, else 1. Pass it only when the user
  asks for more ducks; otherwise leave the user's default alone.
- `--panel-tools <tool,...>` limits which CLIs a panel may use, for example
  `codex,copilot`. It filters each family's routes without reordering them, and
  a family left with no allowed tool is dropped from the panel. The default
  comes from `RUBBER_DUCK_PANEL_TOOLS`, else every tool. It needs a panel, so
  pass it only with `--reviewers` above 1.
- `--reviewer <tool>` forces one reviewer for diagnostics. It overrides a
  `RUBBER_DUCK_REVIEWERS` default but cannot be combined with an explicit
  `--reviewers`, whatever its value.
- `--format json` provides structured metadata for automation.
- `--check --format json` reports installed and authenticated routes without a
  model call.
- `--list-models` reports which models each installed CLI will actually be
  offered, after runtime discovery.

The router prefers a different model family, then Copilot with an explicitly
complementary model, then a fresh isolated session of the caller's own tool.

A panel fills each family's slot from that family's CLI, then from Copilot
brokering a named model of that family. Reviewers run in parallel. A model the
account's plan cannot run (premium requests, quota, plan-gated models) steps
down to the next model on the same tool; throttling or an auth failure skips the
tool. A slot nobody can fill is reported, not padded with a same-family review.
If every slot fails, a disclosed fresh-session review runs instead.

## Act on the critique 🔍

- Verify every finding against the artifact.
- Fix blocking findings that are valid, then re-run relevant validation.
- Adopt non-blocking findings when their benefit is concrete and in scope.
- Reject speculative or scope-expanding advice with a brief reason.
- Permit one re-review when a blocking finding causes a material redesign.
- Always report to the user: the reviewer tool, model, effort, and independence
  level (e.g. "Duck used `agy` (<model>, effort <level>), cross-family."). Pull
  these verbatim from the header line the script emits rather than recalling a
  model name. Never omit this even if the review is brief or the route degraded
  to a self-critique.
- For a panel, report every duck's header, plus the `Panel:` line whenever fewer
  ducks reported than were requested or the panel fell back. Verify each duck's
  findings separately, merge duplicates, and note where the ducks disagree and
  which view you adopted.
- Summarize the key findings and resulting decisions; do not dump the full
  critique unless requested.

If every route fails, perform an explicit in-session self-critique and disclose
the degraded review with `🫠🦆` rather than blocking completion.
