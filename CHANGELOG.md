# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3](https://github.com/lamiskin/pydtsx-parser/compare/v0.1.2...v0.1.3) (2026-08-29)


### Bug Fixes

* dispatch crashed on any .dtproj with no manifest section ([#19](https://github.com/lamiskin/pydtsx-parser/issues/19)) ([60294fb](https://github.com/lamiskin/pydtsx-parser/commit/60294fb3e5c64c1c7d1bd0d81470c98eec38b90b))

## [0.1.2](https://github.com/lamiskin/pydtsx-parser/compare/v0.1.1...v0.1.2) (2026-08-29)


### Bug Fixes

* clear 4 open CodeQL unused-variable notes ([#15](https://github.com/lamiskin/pydtsx-parser/issues/15)) ([a2ea45a](https://github.com/lamiskin/pydtsx-parser/commit/a2ea45ab343f177628f0a6f9c8b90c3c9740ab62))
* release-please needs a real token to trigger publish.yml ([#13](https://github.com/lamiskin/pydtsx-parser/issues/13)) ([8f0a7d0](https://github.com/lamiskin/pydtsx-parser/commit/8f0a7d0b5e3b9382cc6f4dcbe6313b4041bc506e))


### Dependencies

* Bump cryptography from 49.0.0 to 50.0.0 ([#12](https://github.com/lamiskin/pydtsx-parser/issues/12)) ([d4b2ac1](https://github.com/lamiskin/pydtsx-parser/commit/d4b2ac1883bbffdeacaaa8ef6962621133173113))

## [0.1.1](https://github.com/lamiskin/pydtsx-parser/compare/v0.1.0...v0.1.1) (2026-08-29)


### Dependencies

* Bump the python group across 1 directory with 4 updates ([#8](https://github.com/lamiskin/pydtsx-parser/issues/8)) ([0fddbcd](https://github.com/lamiskin/pydtsx-parser/commit/0fddbcd99ab8b9570f756209f53968da2d318933))

## [Unreleased]

## [0.1.0] - 2026-08-29

### Added

- Initial public release.
- Parsers for the four SSIS project file types: `.dtsx` packages, `.dtproj`
  projects, `.conmgr` connection managers, and `.params` project parameters.
- Directory dispatcher that recursively discovers and cross-references all
  files in an SSIS project.
- Data flow pipeline extraction: components, paths, error outputs, and
  topological ordering.
- Control flow extraction: executables, precedence constraints, and Execute SQL
  Task contents.
- Transformation extractors for derived columns, lookups, merge joins, sorts,
  and column mappings.
- Self-describing JSON envelope carrying format/parser versions, source file
  metadata, a data type map, and a completeness summary.
- Automatic credential redaction for sensitive fields and connection strings,
  which deliberately preserves password-like *column* names as schema metadata.
- CLI entry point `pydtsx-parser` with `--output` and `--pretty`.
- Optional MCP server (`pip install "pydtsx-parser[mcp]"`) exposing package
  summary, SQL extraction, and data lineage tools.
- Claude Skill for agent-driven use without a server.
- Type hints throughout, with a PEP 561 `py.typed` marker.

[Unreleased]: https://github.com/lamiskin/pydtsx-parser/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lamiskin/pydtsx-parser/releases/tag/v0.1.0
