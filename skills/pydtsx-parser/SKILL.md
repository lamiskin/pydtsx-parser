---
name: pydtsx-parser
description: Parse and explore SQL Server Integration Services (SSIS) files — .dtsx packages, .dtproj projects, .conmgr connection managers, and .params parameter files. Use when asked to explain what an SSIS package does, extract its SQL, trace data lineage or column mappings, list its connections, determine task execution order, or migrate/document an SSIS ETL estate.
---

# SSIS package parsing

Parse SSIS files into structured JSON with `pydtsx-parser`, then interpret the
result. This skill covers both running the tool and reading its output — SSIS
XML has several non-obvious conventions that are easy to misread.

## Setup

```bash
pip install pydtsx-parser
```

No SSIS installation, SQL Server, or Visual Studio is required.

## Running it

```bash
pydtsx-parser Package.dtsx --pretty              # one file to stdout
pydtsx-parser ./MyProject -p -o project.json     # whole project directory
```

From Python:

```python
from pydtsx_parser.dispatcher import dispatch

result = dispatch("Package.dtsx")
```

Output is large. Prefer extracting the part you need with `jq` or Python over
dumping the whole envelope into context:

```bash
pydtsx-parser Package.dtsx | jq '.content.connection_managers'
pydtsx-parser Package.dtsx | jq '.content.executables[].object_name'
```

## Approach

1. **Orient first.** Read `content.package_attributes`, `connection_managers`,
   and the `object_name`s of `executables`. That answers "what does this package
   touch?" without loading the full pipeline detail.
2. **Then go deep** on the specific data flow or SQL task the user asked about.
3. **Report `completeness_summary`** if the user needs assurance nothing was
   dropped — it carries element and attribute counts from the source XML.

## Control flow vs data flow

These are two distinct layers, and conflating them is the most common mistake:

- **Control flow** is the outer layer: which tasks run, in what order. Tasks are
  connected by precedence constraints (edges conditioned on Success, Failure,
  Completion, or an expression).
- **Data flow** is the inner layer: inside a Data Flow Task
  (`Microsoft.Pipeline`), a pipeline of components moves rows. Sources read,
  transformations modify, destinations write.

Control flow = task orchestration. Data flow = row-level movement.

## Reading the output

### Envelope

| Field | Meaning |
|---|---|
| `content` | The parsed file itself |
| `data_type_map` | Numeric SSIS type codes → names (e.g. `130` → `wstr`) |
| `redaction_summary.total_redacted` | How many credentials were masked |
| `completeness_summary` | Element/attribute counts, proving no data loss |

Data types appear as numeric codes throughout. Resolve them via
`data_type_map` — `130` is `wstr`, `131` is `numeric`, `3` is `i4`.

### Executable types

| `creation_name` | What it does |
|---|---|
| `Microsoft.Pipeline` | Data Flow Task — contains a pipeline |
| `Microsoft.ExecuteSQLTask` | Runs SQL against a connection manager |
| `Microsoft.ExecutePackageTask` | Calls another package |
| `STOCK:SEQUENCE` | Sequence container — grouping only, no logic |
| `STOCK:FORLOOP` / `STOCK:FOREACHLOOP` | Loop containers |

`executables` is **recursive** — containers hold `child_executables`. Always
walk the tree; do not assume a flat list.

### Data flow components

| Classification | Examples |
|---|---|
| `source` | `Microsoft.OLEDBSource`, `Microsoft.FlatFileSource`, `Microsoft.SSISOracleSrc` |
| `destination` | `Microsoft.OLEDBDestination`, `Microsoft.FlatFileDestination` |
| `transformation` | `Microsoft.DerivedColumn`, `Microsoft.Sort`, `Microsoft.MergeJoin`, `Microsoft.ConditionalSplit` |

Notable transformation fields:

- **Derived Column** — `derived_columns[]` with `expression` and
  `friendly_expression`; `is_overwrite` means it replaces an existing column
  rather than adding one.
- **Sort** — `sort_columns[]` with `sort_key_position` and `sort_order`, plus an
  `eliminate_duplicates` flag.
- **Merge Join** — `join_type` (`INNER`/`LEFT`/`FULL`), `join_keys[]`, and
  `treat_nulls_as_equal`. Merge joins require sorted inputs, so they are
  effectively always preceded by Sort components.

### Tracing column lineage

SSIS tracks columns through a pipeline with integer **lineage IDs**, unique
within one data flow:

1. A source assigns a `lineage_id` to each column in `outputs[].output_columns[]`.
2. Downstream components reference it in `inputs[].input_columns[]`.
3. `external_metadata_column_id` links an input column to the destination schema.

To trace source → destination, follow the `lineage_id` chain, then use
`topological_order` for the component processing sequence.

### Precedence constraints

```json
{ "from_task": "Package\\TaskA", "to_task": "Package\\TaskB",
  "eval_op": "Constraint", "value": "Success", "logical_and": true }
```

`value` is `Success`, `Failure`, or `Completion`. When several constraints
target one task, `logical_and: true` means *all* must pass; `false` means *any*.
The constraint array is the execution DAG.

### ID formats

- **DTSID** — a GUID, globally unique per object.
- **refId** — a hierarchical path, e.g. `Package\ConnectionManagers[DW]` or
  `Package\DataFlow\Source.Outputs[Output].Columns[Col1]`.
- **lineage_id** — an integer, unique only within one data flow.

### Missing and null values

- Optional attributes that are absent are **omitted entirely**, not set to null.
- Empty collections are `[]`, never null.
- Redacted values appear as `{"value": "[SENSITIVE - REDACTED]", "sensitive": true}`.
- A component that failed to extract has `extraction_status: "failed"` and a
  `failure_reason` — surface these rather than silently ignoring them.
- An Execute SQL Task with no task data has `sql_data_missing: true`.

## Handling real packages

Passwords are redacted automatically, but redaction is not a full sanitizer.
Parser output still contains internal server names, UNC paths, schema names, the
source file's absolute path, and its filesystem owner.

When the user is working with production packages, do not paste raw parser
output into anything externally visible, and say so if they are about to. Quote
the specific field they asked about instead of the whole envelope.
