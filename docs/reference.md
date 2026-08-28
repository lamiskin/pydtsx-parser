# Usage & API Reference

**pydtsx-parser** extracts the full content of SQL Server Integration Services (SSIS) project files into structured JSON. It reads the raw XML directly — no SSIS installation, SQL Server, or Visual Studio required.

## Installation

```bash
pip install pydtsx-parser
```

With the optional MCP server:

```bash
pip install "pydtsx-parser[mcp]"
```

Requires Python 3.11+. The core package has **zero runtime dependencies**.

For development:

```bash
git clone https://github.com/lamiskin/pydtsx-parser
cd pydtsx-parser
uv sync --all-extras
```

## Quick Start

```bash
pydtsx-parser Package.dtsx --pretty
```

```python
from pydtsx_parser.dispatcher import dispatch

result = dispatch("Package.dtsx")
print(result["file_type"])  # "dtsx_package"
print(result["content"]["package_attributes"]["object_name"])  # package name
```

## CLI Usage

```text
pydtsx-parser <path> [--output FILE] [--pretty]
```

| Argument | Meaning |
|---|---|
| `path` | A file (`.dtsx`, `.dtproj`, `.conmgr`, `.params`) or a directory |
| `--output`, `-o` | Write JSON to a file instead of stdout (parent dirs are created) |
| `--pretty`, `-p` | Pretty-print with 2-space indent |

### Parse a single file

```bash
pydtsx-parser Package.dtsx --pretty
```

### Parse a whole project directory

Recursively discovers all four file types, parses each, and cross-references them:

```bash
pydtsx-parser ./MyProject --pretty --output project.json
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success (including "unsupported file type skipped", which logs a warning) |
| `1` | Path does not exist, parse error, or output file not writable |

Warnings and errors go to **stderr**; JSON goes to **stdout**, so piping into `jq` is always safe.

## Python API

There is no aggregate top-level export — import from the specific module:

### `dispatch(path, pretty=False) -> dict`

The main entry point. Accepts a file or directory path and routes to the right parser. Returns the full envelope (single file) or the combined project document (directory).

```python
from pydtsx_parser.dispatcher import dispatch

envelope = dispatch("Package.dtsx")
project = dispatch("./MyProject")  # directory → combined output
```

### Per-format parsers

Each returns the **content** dict only (no envelope). `dispatch` is the one that wraps content in the envelope and applies redaction.

```python
from pydtsx_parser.parsers.dtsx import parse_dtsx
from pydtsx_parser.parsers.dtproj import parse_dtproj
from pydtsx_parser.parsers.conmgr import parse_conmgr
from pydtsx_parser.parsers.params import parse_params

content = parse_dtsx("Package.dtsx")
```

### `redact(data) -> tuple[dict, int]`

Deep-copies the input and masks credential fields and `Password=` segments inside connection strings. Returns the redacted copy and the number of values masked.

```python
from pydtsx_parser.redaction import redact

clean, count = redact(content)
```

### Low-level extractors

`pydtsx_parser.extractors` exposes the individual building blocks (`extract_pipeline`, `extract_precedence_constraints`, `extract_sql_task`, `extract_variables`, …) for working directly with an XML tree via `pydtsx_parser.xml_utils.parse_xml`. The MCP server is built entirely on these, so they are a supported surface.

## Output Data Structure

### The envelope (single file)

```text
format_version         envelope schema version (independent of package version)
parser_version         pydtsx-parser version that produced the output
source_file_path       absolute path of the parsed file
file_type              dtsx_package | dtproj_project | conmgr_connection | params_parameters
parsed_at              ISO 8601 parse timestamp
source_file_metadata   file_name, file_size_bytes, last_modified, created, owner
data_type_map          numeric SSIS type codes → readable names (130 → wstr, …)
redaction_summary      { total_redacted }
content                the parsed file (shape depends on file_type)
```

### `content` for a `.dtsx` package

```text
package_attributes     object_name, creation_date, creator_name, dts_id, version_guid, …
properties             package-level DTS:Property name/value pairs
variables              name, namespace, data_type, value, scope
connection_managers    object_name, creation_name, dts_id, properties (type-dependent)
executables            recursive task tree — see below
completeness_summary   total_elements, total_attributes, skipped_items
```

Each executable carries `ref_id`, `object_name`, `creation_name` / `executable_type`, `dts_id`, `disabled`, optional `description`, its own `variables`, and — for containers — nested `child_executables`. **Walk the tree recursively**; Sequence containers and loops nest arbitrarily deep.

### `content` for the other file types

| File type | Shape |
|---|---|
| `.dtproj` | `success`, `deployment_model`, `product_version`, `schema_version`, `database`, `manifest` (packages, connection manager refs, protection level), `project_connection_parameters` |
| `.conmgr` | a single `connection_manager` object |
| `.params` | `parameters[]` with name, type, `sensitive`/`required` flags, `default_value` |

### Directory output

```text
directory_path, file_type: "project_directory"
summary                counts: total_files, packages, connection_managers, parameters, projects, errors
packages[]             one entry per file: file_path, file_name, file_type, redaction_count, content
connection_managers[], parameters[], projects[]
cross_references       connection_manager_index, package_connection_references
errors[]               per-file failures with error_type and message
```

For the full semantics — control flow vs data flow, pipeline components, lineage IDs, precedence constraints — see the [LLM context guide](LLM_CONTEXT.md).

## Error Handling

All parser errors derive from `SSISParseError`, which carries `file_path` and `reason`:

```text
SSISParseError            base — "<file_path>: <reason>"
├── FileNotFoundError     file missing or unreadable
├── MalformedXMLError     XML could not be parsed
└── ExtractionError       required element or attribute missing
```

```python
from pydtsx_parser.dispatcher import dispatch
from pydtsx_parser.errors import SSISParseError

try:
    result = dispatch("Package.dtsx")
except SSISParseError as e:
    print(f"Failed on {e.file_path}: {e.reason}")
```

In **directory mode** a broken file never aborts the run — it lands in `errors[]` and the rest of the project still parses. Inside a package, a pipeline component that fails to extract is kept with `extraction_status: "failed"` and a `failure_reason` instead of being dropped.

## Examples

### Extract every SQL statement in a package

Execute SQL Task contents are pulled by a dedicated extractor (the same one
the MCP `get_sql_code` tool uses):

```python
from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.extractors.sql_tasks import extract_sql_task, is_sql_task
from pydtsx_parser.xml_utils import get_root, parse_xml

path = "Package.dtsx"
root = get_root(parse_xml(path), path)
dts = NAMESPACES["DTS"]

for elem in root.iter(f"{{{dts}}}Executable"):
    if is_sql_task(elem.get(f"{{{dts}}}CreationName", "")):
        sql = extract_sql_task(elem, path)
        print(sql["sql_statement_source"])
```

### List every task in execution-relevant detail

```python
from pydtsx_parser.dispatcher import dispatch


def walk(executables, depth=0):
    for exe in executables:
        print("  " * depth + f"{exe['object_name']} ({exe['creation_name']})")
        walk(exe.get("child_executables", []), depth + 1)


walk(dispatch("Package.dtsx")["content"]["executables"])
```

### List connections and where they point

```bash
pydtsx-parser Package.dtsx | jq '
  .content.connection_managers[]
  | {name: .object_name, type: .creation_name,
     cs: .properties.connection_string?}'
```

### Verify completeness

```python
cs = dispatch("Package.dtsx")["content"]["completeness_summary"]
assert not cs["skipped_items"], f"Parser skipped: {cs['skipped_items']}"
```

### Cross-reference a whole project

```bash
pydtsx-parser ./MyProject | jq '.cross_references.package_connection_references'
```

### Check what was redacted

```bash
pydtsx-parser Package.dtsx | jq '.redaction_summary'
```
