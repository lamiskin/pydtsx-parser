# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
