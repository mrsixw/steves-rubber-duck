# Steve's Rubber Duck 🦆🦆🦆

![A chaotic cardboard code-review war room staffed by rubber ducks][duck-war-room]

> **Your Cardboard Engineer 📦👷🦆** — a read-only second opinion from a
> separate capable AI before your plan or code waddles into production.

Steve's Rubber Duck is a shared agent skill that routes plans and completed
changes to Claude, Codex, GitHub Copilot, or Google Antigravity (`agy`). It
prefers a different model family, falls back through operational tools, and
finally asks a fresh instance of the caller when no independent family is
available. 🦆🔀🧠

The design follows the high-signal behavior of [GitHub Copilot's Rubber Duck
agent][github-rubber-duck], while making the pattern available across multiple
agent CLIs.

## Why? 🤔🦆

Because this:

![An overconfident duck presents a perfect plan before the second-model duck squad arrives][plan-review-meme]

...often prevents this:

![A duck celebrates passing tests before another duck finds a bug in the diff][code-review-meme]

## What the duck reviews 🔍🦆

- `🦆📋` Completed non-trivial plans before presentation or implementation.
- `🦆🔍` Final scoped code changes after validation.
- `🚨🦆` Blocking correctness, security, compatibility, or data-loss risks.
- `⚠️🦆` Concrete non-blocking quality and maintainability issues.
- `💡🦆` Optional improvements with a practical benefit.
- `✅🦆 QUACKS GOOD` when there are no substantive findings.

Cosmetic style, naming preferences, grammar nits, and generic best-practice
lectures stay out of the pond. 🌊🚫

## Routing order 🔀🦆

1. An authenticated direct CLI from a different model family.
2. Copilot's native Rubber Duck agent using an explicitly complementary model.
3. A fresh isolated session from the caller's own CLI.
4. A clearly disclosed in-session self-critique when every route fails. `🫠🦆`

Installed does not automatically mean operational: Claude and Codex use their
stable authentication checks, while Copilot and AGY are verified by the actual
bounded review call.

## Usage 🚀🦆

The skill normally invokes the router for you. To inspect available routes
without spending a model call:

```bash
python3 scripts/steves_rubber_duck.py --check
python3 scripts/steves_rubber_duck.py --check --format json
```

To review a plan explicitly:

```bash
printf '%s' "$PLAN" | python3 scripts/steves_rubber_duck.py \
  --caller codex \
  --caller-family openai \
  --kind plan \
  --tier auto
```

To review a validated diff with a forced reviewer:

```bash
git diff --no-ext-diff | python3 scripts/steves_rubber_duck.py \
  --caller claude \
  --caller-family anthropic \
  --kind code \
  --reviewer codex \
  --tier high
```

Use `--format json` for automation. Human output is deliberately duck-heavy;
JSON field names remain conventional and stable. 🦆🤝🤖

## Capability tiers 🧠🦆

`--tier auto` uses a capable medium model normally and promotes reviews to a
high-capability model for security, production infrastructure, destructive
operations, migrations, concurrency, public interfaces, architectural work,
or repeated uncertainty.

Model identifiers can be overridden without editing the skill:

```text
RUBBER_DUCK_<TOOL>_<FAMILY>_<TIER>_MODEL
RUBBER_DUCK_CODEX_MODEL
RUBBER_DUCK_TIMEOUT_SECONDS
```

## Safety rails 🛟🦆

- Reviewer sessions run from an isolated temporary directory.
- Editing and shell tools are disabled where the CLI supports it.
- The reviewer receives only the packet supplied on standard input.
- `RUBBER_DUCK_CHILD=1` prevents recursive ducks summoning more ducks forever.
- The router writes no repository files or review history.
- Provider CLIs may retain their normal local account or session caches.
- Review packets larger than 500 KB must be split by subsystem.

## Installation 🧰🦆

The canonical personal skill lives at:

```text
~/.agents/skills/steves-rubber-duck
```

Codex, Claude, and Copilot can link to that directory. AGY uses a global
Markdown link at:

```text
~/.gemini/antigravity-cli/skills/steves-rubber-duck.md
```

## Development 🧪🦆

The router uses only the Python standard library.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/steves_rubber_duck.py --check --format json
```

Licensed under the [MIT License][license].

![Steve's cardboard-engineer rubber duck mascot][cardboard-engineer]

---

[cardboard-engineer]: assets/cardboard-engineer-mascot.png
[code-review-meme]: assets/code-review-meme.png
[duck-war-room]: assets/duck-war-room.png
[github-rubber-duck]: https://docs.github.com/en/copilot/concepts/agents/copilot-cli/rubber-duck
[license]: LICENSE
[plan-review-meme]: assets/plan-review-meme.png
