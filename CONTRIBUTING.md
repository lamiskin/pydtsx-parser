# Contributing

Thanks for your interest in improving `pydtsx-parser`.

## The one rule that matters most

**Never contribute real SSIS packages, extracts, or production data.**

SSIS files are unusually leaky: they routinely embed internal server names, UNC
paths, database schemas, domain usernames, and sometimes credentials. Everything
in this repository — every test input, every example, every issue attachment —
must be synthetic.

If you are debugging against a real package, reduce it to a minimal synthetic
snippet that reproduces the behaviour before opening an issue or PR.

## Setup

This project uses [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/lamiskin/pydtsx-parser
cd pydtsx-parser
uv sync --all-extras
uv run pre-commit install
```

## Everyday commands

```bash
uv run pytest                    # run the test suite
uv run pytest --cov             # with coverage
uv run ruff check --fix         # lint
uv run ruff format              # format
uv run mypy                     # type check
```

All four must pass before a PR can merge; CI runs them on Python 3.11–3.14
across Linux, Windows, and macOS.

## Testing against your own packages

Integration tests look for an optional `examples/` directory at the repository
root and skip cleanly when it is absent. You can drop your own SSIS projects
there to exercise the parser locally — `examples/` is gitignored, so they will
not be committed. Keep it that way.

## Commit messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/).
Release automation reads them, so the prefix determines the version bump:

| Prefix | Effect |
|---|---|
| `fix:` | patch release |
| `feat:` | minor release |
| `feat!:` or `BREAKING CHANGE:` | major release |
| `docs:`, `ci:`, `test:`, `chore:`, `refactor:` | no release |

Example: `feat: extract Lookup transformation cache settings`

## Releases are automated

Do not bump versions or edit `CHANGELOG.md` by hand.
[release-please](https://github.com/googleapis/release-please) watches `main`,
maintains a release PR, and merging it tags a GitHub Release, which publishes to
PyPI via Trusted Publishing.

### Bootstrapping the first release (maintainers)

release-please treats `.release-please-manifest.json` as the last *released*
version, so it will only ever propose versions **after** it. The version
currently recorded there has to be tagged and released by hand once, or it never
reaches PyPI:

```bash
git tag -a v1.0.0 -m "pydtsx-parser 1.0.0" && git push origin v1.0.0
gh release create v1.0.0 --notes-from-tag
```

Before that, dry-run the whole pipeline without touching real PyPI: run the
**Publish** workflow manually (`workflow_dispatch`) with target `testpypi`. It
builds, validates the metadata, smoke-tests the wheel, and publishes to TestPyPI
only — the PyPI job is unreachable from that trigger.

## Adding a new extractor

Extractors live in `pydtsx_parser/extractors/` and take an `ET.Element`,
returning plain dicts and lists. Keep them pure — file I/O belongs in
`pydtsx_parser/parsers/`. Add the extractor to the relevant parser, then cover
it with both example-based tests and, where the shape allows, a Hypothesis
property test.
