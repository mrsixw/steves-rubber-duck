# Contributing 🦆

Thanks for helping the duck. 📦👷🦆

## Development

The router uses only the Python standard library. There is nothing to install
and nothing to build.

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/steves_rubber_duck.py
python3 scripts/steves_rubber_duck.py --check --format json
python3 scripts/steves_rubber_duck.py --list-models --format json
```

The [Tests workflow][tests-workflow] runs the suite, a compile check, and a
catalog validation across the supported Python versions.

## Updating models 📇

Models live in [`data/models.json`](data/models.json), never in the router.
To refresh one, edit the JSON and set `updated` to today. Keep the superseded
model in the list as a fallback rather than deleting it.

Run `--list-models` afterwards to confirm the entries resolve, and remember that
a model a CLI does not report is filtered out at runtime where discovery is
supported.

## Commit messages

Commits follow [Conventional Commits][conventional]. This is not cosmetic: the
release version is derived from them.

| Prefix | Effect on the version |
| --- | --- |
| `feat:` | minor bump |
| `fix:`, `docs:`, `chore:`, `refactor:`, `test:` | patch bump |
| `feat!:` or a `BREAKING CHANGE:` footer | major bump |

A push with no recognisable prefix falls back to a patch bump, per
`whenNoValidCommitMessages` in [`mkver.conf`](mkver.conf).

## Versioning 🔢

[`VERSION`](VERSION) is the single source of truth, read at runtime by
`--version` and reported in `--check`, `--list-models`, and the JSON review
metadata.

> [!WARNING]
> Do **not** run `git mkver patch` on a feature branch. It rewrites `VERSION`,
> and the release job bumps the version itself. Version changes belong to a
> release, not to regular development.

## Releases 🏷️

Releases are created automatically by CI on every push to `main`, except for the
`chore: bump version` commits the release process itself pushes. The `release`
job:

1. Reads `VERSION`.
2. If that version is already tagged, runs `git mkver patch` to bump it, commits
   `chore: bump version to X.Y.Z`, and pushes it to `main`.
3. Runs `gh release create vX.Y.Z --generate-notes`.

GitHub generates the notes from merged PR titles, so **a good PR title becomes a
good release note**.

A `verify-release` job then clones the published tag exactly as a user would and
checks that the released router reports its version and can enumerate its
catalog. A release that cannot do that is broken for everyone who clones it.

The release carries no built artifacts. The skill is installed by cloning the
repository, so the tag and its notes are the deliverable.

### Why releases matter here

The skill is installed with `git clone` and updated with `git pull --ff-only`,
so an unreleased `main` reaches users the moment it is pushed. Tags give a
recoverable point, and the generated notes are what tell someone running a stale
clone why they should pull — which matters most when a model is retired and a
stale catalog starts routing to something that no longer exists.

[conventional]: https://www.conventionalcommits.org/
[tests-workflow]: https://github.com/mrsixw/steves-rubber-duck/actions/workflows/tests.yml
