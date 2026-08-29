# pydtsx-parser

[![CI](https://github.com/lamiskin/pydtsx-parser/actions/workflows/ci.yml/badge.svg)](https://github.com/lamiskin/pydtsx-parser/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/lamiskin/pydtsx-parser/branch/main/graph/badge.svg)](https://codecov.io/gh/lamiskin/pydtsx-parser)
[![PyPI](https://img.shields.io/pypi/v/pydtsx-parser.svg)](https://pypi.org/project/pydtsx-parser/)
[![Python versions](https://img.shields.io/pypi/pyversions/pydtsx-parser.svg)](https://pypi.org/project/pydtsx-parser/)
[![CodeQL](https://github.com/lamiskin/pydtsx-parser/actions/workflows/codeql.yml/badge.svg)](https://github.com/lamiskin/pydtsx-parser/actions/workflows/codeql.yml)
[![Docs](https://img.shields.io/badge/docs-lamiskin.github.io-blue)](https://lamiskin.github.io/pydtsx-parser/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Parse SQL Server Integration Services (SSIS) project files into structured,
self-describing JSON — with no SSIS installation, no SQL Server, and no runtime
dependencies.

Handles the four file types that make up an SSIS project:

| File | What it holds |
|---|---|
| `.dtsx` | Packages: control flow, data flow pipelines, variables, connections |
| `.dtproj` | Project manifest, deployment model, package list |
| `.conmgr` | Project-level connection managers |
| `.params` | Project parameters |

## Why

SSIS packages are large, deeply nested XML files that are painful to read and
awkward to diff. If you are migrating away from SSIS, auditing what a package
actually does, or documenting an inherited ETL estate, you need the *structure*
out of that XML — task graphs, data lineage, embedded SQL, column mappings —
without opening Visual Studio.

`pydtsx-parser` extracts all of it into one JSON envelope designed to be
machine-readable and self-describing: the output carries its own data type map
and a completeness summary of how many elements and attributes were seen.

## Supported SSIS versions

The parser is **version-agnostic by design**: it has no version gates and no
version-specific branches. Version markers such as `LastModifiedProductVersion`
and the `.dtproj` `ProductVersion` are extracted and reported, but they never
change how a file is parsed. "Supported" below therefore means *verified*, not
*enabled* — an unlisted version is likely to parse.

| SQL Server / SSIS | Package format | Status | Verified by |
|---|---|---|---|
| **2012** (11.0) | `SSIS.Package.3` | Real package | `u2_toolkit/Package.dtsx`, `u2_toolkit/Project.dtproj` |
| **2014** (12.0) | `Microsoft.Package` | Real package | `u2_toolkit/PackageAzure.dtsx` |
| **2019** (15.0) | `Microsoft.Package` | Synthetic fixtures | hand-written packages across the suite |
| **2022** (16.0) | `Microsoft.Package` | Real packages | the four `ssis_examples/*.dtsx` |
| 2016 / 2017 (13.0 / 14.0) | `Microsoft.Package` | Expected to work, untested | bracketed by the 2014 and 2019 cases |
| 2008 and earlier | `SSIS.Package.2` and older | Unknown | no sample available; predates the `.dtproj` project deployment model |

Both package format generations are covered by real files: the older
`SSIS.Package.3` form used by SSIS 2012, and the `Microsoft.Package` form used
from 2014 onward. The real fixtures also span OLE DB, Flat File and ADO.NET
connection managers — including a third-party ADO.NET provider — and both
friendly-name and raw-GUID pipeline component class IDs.

Two gaps worth stating plainly:

- Only the **project deployment model** is verified. The single real `.dtproj`
  declares `DeploymentModel=Project` (schema `9.0.1.0`); the legacy package
  deployment model has no real-file coverage.
- No real `.conmgr` file was available, so project-level connection managers are
  covered by synthetic fixtures only.

Provenance and the sanitisation applied to the real fixtures are documented in
[`tests/fixtures/real_world/README.md`](tests/fixtures/real_world/README.md).

### Handling unknown content

With no version gating, an unfamiliar package generally parses. The
`completeness_summary` on every parse result reports `total_elements` and
`total_attributes` actually seen, so you can check a package was read in full
rather than trusting silence. Note that its `skipped_items` field lists XML
comments and processing instructions — deliberately ignored content — not
elements the parser failed to understand.

Unrecognised executables and pipeline components are still emitted with their
attributes and properties intact, keyed by whatever `CreationName` or
`componentClassID` the file declares, so a third-party or newer component
appears in the output even when the parser has no special knowledge of it.

## Install

```bash
pip install pydtsx-parser
```

With the optional MCP server:

```bash
pip install "pydtsx-parser[mcp]"
```

Requires Python 3.11+.

## Quick start

Parse a single package:

```bash
pydtsx-parser Package.dtsx --pretty
```

Parse an entire project directory (recursively discovers all four file types and
cross-references them):

```bash
pydtsx-parser ./MyProject --pretty --output project.json
```

From Python:

```python
from pydtsx_parser.dispatcher import dispatch

result = dispatch("Package.dtsx")
print(result["content"]["package_attributes"]["object_name"])
```

### Output shape

```json
{
  "format_version": "1.0.0",
  "parser_version": "0.1.0",
  "source_file_path": "/path/to/Package.dtsx",
  "file_type": "dtsx_package",
  "parsed_at": "2026-01-01T09:00:00+10:00",
  "source_file_metadata": { "file_name": "Package.dtsx", "file_size_bytes": 724, "owner": "..." },
  "data_type_map": { "130": "wstr", "131": "numeric", "...": "..." },
  "redaction_summary": { "total_redacted": 0 },
  "content": {
    "package_attributes": { "object_name": "LoadCustomers", "...": "..." },
    "variables": [ { "name": "BatchDate", "namespace": "User", "data_type": "7" } ],
    "connection_managers": [ { "object_name": "DW", "creation_name": "OLEDB" } ],
    "executables": [],
    "completeness_summary": { "total_elements": 6, "total_attributes": 11, "skipped_items": [] }
  }
}
```

## CLI

```
usage: pydtsx-parser [-h] [--output OUTPUT] [--pretty] path

Parse SSIS files (.dtsx, .dtproj, .conmgr, .params) into JSON.

positional arguments:
  path                  File or directory path to parse

options:
  -h, --help            show this help message and exit
  --output OUTPUT, -o OUTPUT
                        Output file path (default: stdout)
  --pretty, -p          Pretty-print JSON with 2-space indent
```

## Credential redaction

Passwords are redacted automatically — both as standalone fields and inside
connection strings:

```python
from pydtsx_parser.redaction import redact

redact({"connection_string": "Data Source=dbhost;User ID=svc;Password=hunter2;"})
# ({'connection_string': 'Data Source=dbhost;User ID=svc;Password=[SENSITIVE - REDACTED];'}, 1)
```

Schema metadata is deliberately left intact — a *column* named `PASSWORD_HASH`
is structure, not a secret, so it is not redacted.

### Handling real packages

Redaction covers credentials, not everything an SSIS file can reveal. Parser
output also includes the source file's absolute path and its filesystem owner,
and packages routinely embed internal server names, UNC paths, and schema names.
Review parser output before attaching it to a public issue or sharing it outside
your organisation.

## MCP server

`pydtsx-parser` ships an optional [MCP](https://modelcontextprotocol.io) server
so agents can explore SSIS packages directly. Install the extra, then point your
client at the `pydtsx-parser-mcp` command:

```json
{
  "mcpServers": {
    "pydtsx-parser": {
      "command": "pydtsx-parser-mcp"
    }
  }
}
```

Tools provided:

| Tool | Purpose |
|---|---|
| `get_package_summary` | High-level overview — best first call |
| `get_sql_code` | Extract embedded SQL statements |
| `get_data_lineage` | Control flow edges plus source → destination tracing |
| `get_data_flows` | Full data flow component detail and column mappings |
| `parse_dtsx_file` | Full structured JSON for one file |
| `parse_ssis_directory` | Full structured JSON for a project |

A [Claude Skill](skills/pydtsx-parser/SKILL.md) is also included, for a
portable, dependency-free way to teach an agent how to use the CLI.

## Documentation

Full documentation lives at
**[lamiskin.github.io/pydtsx-parser](https://lamiskin.github.io/pydtsx-parser/)** —
including the [LLM context guide](docs/LLM_CONTEXT.md), a deep reference for
interpreting the JSON output.

## Development

```bash
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
uv run mypy
```

The test suite is fully synthetic — every input is constructed in-memory or
written to a temp directory. No SSIS packages are bundled with this repository.
Integration tests look for an optional local `examples/` directory and skip
cleanly when it is absent, so you can point them at your own packages without
ever committing them.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## Acknowledgements

This project was developed with AI assistance and validated against real-world
SSIS projects. **None of that data, its identifiers, or its history is included
in this repository** — no packages, no extracts, no connection details. The
tests run entirely on synthetic fixtures.

## License

MIT — see [LICENSE](LICENSE).

SQL Server and SQL Server Integration Services are trademarks of Microsoft
Corporation. This project is not affiliated with or endorsed by Microsoft.
