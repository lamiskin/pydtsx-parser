# pydtsx-parser

Parse SQL Server Integration Services (SSIS) project files into structured,
self-describing JSON — with no SSIS installation, no SQL Server, and no runtime
dependencies.

It handles the four file types that make up an SSIS project:

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

With the optional [MCP server](ai-integration.md):

```bash
pip install "pydtsx-parser[mcp]"
```

Requires Python 3.11+.

## Quick start

Parse a single package:

```bash
pydtsx-parser Package.dtsx --pretty
```

Parse an entire project directory (recursively discovers all four file types
and cross-references them):

```bash
pydtsx-parser ./MyProject --pretty --output project.json
```

From Python:

```python
from pydtsx_parser.dispatcher import dispatch

result = dispatch("Package.dtsx")
```

Output is large — prefer extracting the part you need:

```bash
pydtsx-parser Package.dtsx | jq '.content.connection_managers'
pydtsx-parser Package.dtsx | jq '.content.executables[].object_name'
```

## Credential redaction

Passwords are redacted automatically — both as standalone fields and inside
connection strings. Schema metadata is deliberately left intact: a *column*
named `PASSWORD_HASH` is structure, not a secret.

!!! warning "Handling real packages"
    Redaction covers credentials, not everything an SSIS file can reveal.
    Parser output also includes the source file's absolute path and its
    filesystem owner, and packages routinely embed internal server names, UNC
    paths, and schema names. Review parser output before attaching it to a
    public issue or sharing it outside your organisation.

## Understanding the output

- The **[usage & API reference](reference.md)** covers the CLI, the Python
  API, the output data structure, and error handling, with worked examples.
- The **[LLM context guide](LLM_CONTEXT.md)** documents the JSON semantics in
  depth — control flow vs data flow, the recursive executables tree,
  precedence constraints, lineage IDs, and common analysis recipes. It is
  written to be pasted into an LLM's context, but it doubles as the human
  reference for interpreting the output.

## Links

- [Source on GitHub](https://github.com/lamiskin/pydtsx-parser)
- [PyPI package](https://pypi.org/project/pydtsx-parser/)
- [Changelog](https://github.com/lamiskin/pydtsx-parser/blob/main/CHANGELOG.md)
- [Contributing](https://github.com/lamiskin/pydtsx-parser/blob/main/CONTRIBUTING.md)
