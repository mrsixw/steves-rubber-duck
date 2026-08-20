---
name: steves-rubber-duck
description: Obtain a read-only second opinion from a separate capable AI model on non-trivial implementation plans and completed code changes. Use automatically before presenting or implementing a substantial plan and before declaring substantial changes complete; use explicitly when asked to rubber-duck, critique, review, or get a second opinion. Skip trivial edits and never invoke from an existing RUBBER_DUCK_CHILD review.
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
- Skip automatic review for simple factual answers, obvious one-line edits, and
  cosmetic-only changes. Honor an explicit review request regardless of size.

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

- `--reviewer <tool>` forces one reviewer for diagnostics.
- `--format json` provides structured metadata for automation.
- `--check --format json` reports installed and authenticated routes without a
  model call.
- `--list-models` reports which models each installed CLI will actually be
  offered, after runtime discovery.

The router prefers a different model family, then Copilot with an explicitly
complementary model, then a fresh isolated session of the caller's own tool.

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
- Summarize the key findings and resulting decisions; do not dump the full
  critique unless requested.

If every route fails, perform an explicit in-session self-critique and disclose
the degraded review with `🫠🦆` rather than blocking completion.
