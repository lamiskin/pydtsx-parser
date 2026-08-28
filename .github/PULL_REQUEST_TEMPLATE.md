## What does this change?

<!-- A short description, and the issue it closes if applicable. -->

## Checklist

- [ ] **No real or confidential data included** — no production SSIS packages,
      server names, credentials, UNC paths, or personal data in code, tests,
      fixtures, or this description
- [ ] Tests added or updated, and all inputs are synthetic
- [ ] `uv run pytest` passes
- [ ] `uv run ruff check` and `uv run ruff format --check` pass
- [ ] `uv run mypy` passes
- [ ] Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
      (`feat:`, `fix:`, `docs:`, `ci:` …) so release automation picks them up
- [ ] CHANGELOG entry is not needed (release-please generates it from commits)
