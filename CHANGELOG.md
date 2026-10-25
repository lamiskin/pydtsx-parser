# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.8](https://github.com/lamiskin/pydtsx-parser/compare/v0.1.7...v0.1.8) (2026-10-25)


### Dependencies

* bump certifi from 2026.7.22 to 2026.10.19 ([0de831a](https://github.com/lamiskin/pydtsx-parser/commit/0de831a2c59cfeea035d0d7f32a652b565ccc884))
* bump filelock from 3.32.0 to 4.2.1 ([228e2f2](https://github.com/lamiskin/pydtsx-parser/commit/228e2f2af2dd386dd8d44ad6f2f6ea7476f52d7f))
* bump opentelemetry-api from 1.44.0 to 1.45.1 ([02499c0](https://github.com/lamiskin/pydtsx-parser/commit/02499c03bc1d239a7c415f81d1ad8ef0c6d0a882))
* bump virtualenv from 21.7.13 to 21.14.13 ([#38](https://github.com/lamiskin/pydtsx-parser/issues/38)) ([b792e34](https://github.com/lamiskin/pydtsx-parser/commit/b792e34e75f640cd0644e3dcd49a032ecab072be))

## [0.1.7](https://github.com/lamiskin/pydtsx-parser/compare/v0.1.6...v0.1.7) (2026-10-10)


### Dependencies

* bump mcp ([#34](https://github.com/lamiskin/pydtsx-parser/issues/34)) ([235ac70](https://github.com/lamiskin/pydtsx-parser/commit/235ac707601ff5e48a158f38260342fae4b6ac42))
* bump pyjwt from 2.13.0 to 2.15.0 ([#30](https://github.com/lamiskin/pydtsx-parser/issues/30)) ([eb416be](https://github.com/lamiskin/pydtsx-parser/commit/eb416bea22733ab1466079284ffb86e010508b13))
* bump urllib3 from 2.7.0 to 2.8.0 ([#31](https://github.com/lamiskin/pydtsx-parser/issues/31)) ([019f894](https://github.com/lamiskin/pydtsx-parser/commit/019f894c0b6e035f763956c812c8647ff0388b3e))
* bump virtualenv from 21.7.0 to 21.7.13 ([#32](https://github.com/lamiskin/pydtsx-parser/issues/32)) ([73c645a](https://github.com/lamiskin/pydtsx-parser/commit/73c645a07f2506813ce339047ad436e98b4b7b3b))

## [0.1.6](https://github.com/lamiskin/pydtsx-parser/compare/v0.1.5...v0.1.6) (2026-09-22)


### Dependencies

* bump the python group with 2 updates ([#26](https://github.com/lamiskin/pydtsx-parser/issues/26)) ([40e60e9](https://github.com/lamiskin/pydtsx-parser/commit/40e60e9971202e411d7734219c3696143146aea1))

## [0.1.5](https://github.com/lamiskin/pydtsx-parser/compare/v0.1.4...v0.1.5) (2026-09-14)


### Dependencies

* bump the python group with 2 updates ([#24](https://github.com/lamiskin/pydtsx-parser/issues/24)) ([2fed5ad](https://github.com/lamiskin/pydtsx-parser/commit/2fed5adcbd9e0b3aacd57c0b7077dccda8c27b68))

## [0.1.4](https://github.com/lamiskin/pydtsx-parser/compare/v0.1.3...v0.1.4) (2026-09-08)


### Dependencies

* bump the python group with 2 updates ([#21](https://github.com/lamiskin/pydtsx-parser/issues/21)) ([2c0cbcf](https://github.com/lamiskin/pydtsx-parser/commit/2c0cbcf13b059b0dd2b0995b57cae2f00621960b))

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
