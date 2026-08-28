# LLM Context Guide: Understanding pydtsx-parser JSON Output

This document is designed to be included as context for Large Language Models (LLMs) that need to consume, analyze, or answer questions about the JSON output produced by pydtsx-parser. It provides the semantic understanding that raw JSON alone cannot convey.

---

## What is an SSIS Project?

SQL Server Integration Services (SSIS) is Microsoft's ETL platform. An SSIS project is a set of XML files authored in Visual Studio:

| File | What it holds |
|---|---|
| `.dtsx` | A package: control flow, data flow pipelines, variables, connections |
| `.dtproj` | The project manifest: deployment model, package list, project parameters |
| `.conmgr` | A project-level (shared) connection manager |
| `.params` | Project parameters |

pydtsx-parser reads these files directly — no SSIS installation or SQL Server required — and emits one JSON document per file, or a combined project document for a directory.

---

## The Output Envelope

Every parsed file is wrapped in a self-describing envelope:

```
format_version        → version of the envelope schema itself
parser_version        → version of pydtsx-parser that produced the output
source_file_path      → absolute path of the parsed file
file_type             → "dtsx_package" | "dtproj_project" | "conmgr_connection" | "params_parameters"
parsed_at             → ISO 8601 timestamp of the parse
source_file_metadata  → file_name, file_size_bytes, last_modified, created, owner
data_type_map         → numeric SSIS type codes → readable names
redaction_summary     → { total_redacted: <count of masked credentials> }
content               → the parsed file itself
```

Two fields deserve special attention:

- **`data_type_map`** — SSIS stores column data types as numeric codes (`130`, `131`, `3`, …). Whenever you see a numeric `data_type`, resolve it here: `130` is `wstr` (Unicode string), `131` is `numeric`, `3` is `i4` (32-bit int).
- **`redaction_summary`** — passwords and credential fields are masked before output. A redacted value appears as `{"value": "[SENSITIVE - REDACTED]", "sensitive": true}`. Schema metadata (e.g. a *column* named `PASSWORD_HASH`) is deliberately left intact.

Note that `source_file_path`, `source_file_metadata.owner`, and embedded server names are **not** redacted — treat parser output as containing whatever the source package contained.

### Directory output

Parsing a directory returns a combined document instead:

```
directory_path, file_type: "project_directory"
summary            → counts of total_files, packages, connection_managers, parameters, projects, errors
packages[]         → one entry per .dtsx  ── each has file_path, file_name, file_type, redaction_count, content
connection_managers[], parameters[], projects[]   → same shape for the other file types
cross_references   → connection_manager_index (name → file), package_connection_references (package → CM names)
errors[]           → files that failed to parse, with error_type and message
```

Use `cross_references` to answer "which packages use connection manager X?" without re-scanning content.

---

## Control Flow vs Data Flow

These are two distinct layers, and conflating them is the most common interpretation mistake:

- **Control flow** is the outer layer: which tasks run, in what order. Tasks (`executables`) are connected by **precedence constraints** — edges conditioned on Success, Failure, Completion, or an expression.
- **Data flow** is the inner layer: inside a Data Flow Task (`creation_name: "Microsoft.Pipeline"`), a pipeline of components moves rows. Sources read, transformations modify, destinations write.

Control flow = task orchestration. Data flow = row-level movement.

---

## `content` for a `.dtsx` Package

```
package_attributes     → identity: object_name, creation_date, creator_name,
                         creator_computer_name, dts_id, version_guid, locale_id, …
properties             → package-level DTS:Property name/value pairs
variables              → package variables: name, namespace, value, data type
connection_managers    → data source definitions (see below)
executables            → the control-flow task tree (RECURSIVE — see below)
completeness_summary   → total_elements, total_attributes, skipped_items
```

### `executables` is a tree, not a list

Container tasks hold nested tasks in `child_executables`. **Always walk the tree recursively**; a flat read misses everything inside Sequence containers and loops.

| `creation_name` | What it is |
|---|---|
| `Microsoft.Pipeline` | Data Flow Task — contains a pipeline of components |
| `Microsoft.ExecuteSQLTask` | Runs SQL against a connection manager |
| `Microsoft.ExecutePackageTask` | Invokes another package |
| `STOCK:SEQUENCE` | Sequence container — grouping only, no logic of its own |
| `STOCK:FORLOOP` / `STOCK:FOREACHLOOP` | Loop containers |

### Precedence constraints

```json
{ "from_task": "Package\\TaskA", "to_task": "Package\\TaskB",
  "eval_op": "Constraint", "value": "Success", "logical_and": true }
```

- `value` — the condition: `Success`, `Failure`, or `Completion`.
- `eval_op` — `Constraint` (result only), `Expression`, or combined forms; when an expression is involved, the `expression` field holds it.
- `logical_and` — when several constraints target one task: `true` = **all** must pass, `false` = **any** may pass.

The constraint array **is** the execution DAG of the control flow.

### Execute SQL Tasks

Each SQL task exposes `sql_statement_source` (the SQL text), `sql_source_type`, `connection` (a connection manager reference), `is_stored_procedure`, and `parameter_bindings`. A task whose task-data element is missing has `sql_data_missing: true` — report that rather than treating it as "no SQL".

### Connection managers

Each has `object_name`, `creation_name` (the type: `OLEDB`, `ADO.NET:SQL`, `FLATFILE`, `ORACLE`, …), `dts_id`, optional `description`, and a `properties` dict whose keys depend on the type — e.g. `connection_string` for OLEDB/ADO.NET, or `format` / `locale_id` / `code_page` / `flat_file_columns[]` for flat files. Server and database names live inside `connection_string` (`Data Source=…;Initial Catalog=…`).

---

## Data Flow Pipelines

Each `Microsoft.Pipeline` executable contains a pipeline with:

```
components[]        → sources, transformations, destinations
paths[]             → edges wiring component outputs to downstream inputs
topological_order[] → component processing sequence, first to last
error_outputs[]     → error-path wiring
```

### Component classification

Every component carries a `classification`:

| Classification | Examples (`component_class_id`) |
|---|---|
| `source` | `Microsoft.OLEDBSource`, `Microsoft.FlatFileSource`, `Microsoft.SSISOracleSrc` |
| `destination` | `Microsoft.OLEDBDestination`, `Microsoft.FlatFileDestination` |
| `transformation` | `Microsoft.DerivedColumn`, `Microsoft.Sort`, `Microsoft.MergeJoin`, `Microsoft.ConditionalSplit`, `Microsoft.Lookup` |

For sources, the query or table being read is in `custom_properties`: look for `SqlCommand` (a SQL statement) or `OpenRowset` (a table/view name).

### Notable transformation fields

- **Derived Column** — `derived_columns[]` with `expression` and `friendly_expression`; `is_overwrite: true` means it replaces an existing column rather than adding one.
- **Sort** — `sort_columns[]` with `sort_key_position` and `sort_order`, plus an `eliminate_duplicates` flag.
- **Merge Join** — `join_type` (`INNER`/`LEFT`/`FULL`), `join_keys[]`, `treat_nulls_as_equal`. Merge joins require sorted inputs, so they are effectively always fed by Sort components.

### Column lineage

SSIS tracks columns through a pipeline with integer **lineage IDs**, unique within one data flow:

1. A source assigns a `lineage_id` to each column in `outputs[].output_columns[]`.
2. Downstream components reference that id in `inputs[].input_columns[]`.
3. `external_metadata_column_id` links an input column to the destination's external schema.

To trace a column source → destination, follow its `lineage_id` chain along `paths`, using `topological_order` for the processing sequence. Outputs with `is_error_out: true` are error paths, not the main data path.

---

## `content` for the Other File Types

### `.dtproj`

```
success, deployment_model ("Project" | "Package"), product_version, schema_version
database          → { name } of the embedded .database node
manifest          → protection_level, project_properties, packages[] (name, entry_point),
                    connection_managers[] (project-level CM file references)
project_connection_parameters[]  → name, sensitive flag; sensitive params carry no value
```

### `.conmgr`

A single `connection_manager` object with the same shape as an in-package connection manager (`object_name`, `creation_name`, `dts_id`, `properties`).

### `.params`

`parameters[]` with name, data type, `sensitive` and `required` flags, and `default_value`. Sensitive parameters have their values withheld.

---

## ID Formats

| ID | Shape | Scope |
|---|---|---|
| `dts_id` / DTSID | `{GUID}` | Globally unique per object |
| `ref_id` / refId | Hierarchical path: `Package\ConnectionManagers[DW]`, `Package\DataFlow\Source.Outputs[Output].Columns[Col1]` | Unique within a package; encodes containment |
| `lineage_id` | Integer | Unique only within one data flow |

The `from_task` / `to_task` values in precedence constraints are refIds — the segment after the last `\` is the task's display name.

---

## Missing and Null Values

- Optional XML attributes that are absent are **omitted entirely** from the JSON, not set to null.
- Empty collections are `[]`, never null.
- A pipeline component that failed to extract has `extraction_status: "failed"` and a `failure_reason` — surface these rather than silently ignoring them.
- `completeness_summary` counts every element and attribute seen in the source XML; use it to assure users nothing was dropped, and report `skipped_items` if non-empty.

---

## Common Analysis Tasks

### "What does this package do?"

1. Read `content.package_attributes.object_name` for the package name.
2. Walk `content.executables` (recursively) and list `object_name` / `creation_name` per task.
3. Order tasks using the precedence constraints (`from_task` → `to_task`).
4. For each `Microsoft.Pipeline`, summarize its components by `classification`.

### "What SQL does it run?"

1. Collect `sql_statement_source` from every Execute SQL Task in the executables tree.
2. Collect `SqlCommand` / `OpenRowset` custom properties from every pipeline source component.

### "What does it read and write?"

1. `connection_managers[].properties.connection_string` → servers and databases.
2. Pipeline `source` components → tables/queries read; `destination` components → tables written (see their `custom_properties` and external metadata).

### "What is the execution order?"

- Control flow: build the DAG from precedence constraints; tasks with no incoming edge start first.
- Data flow: `topological_order` inside each pipeline is already sorted.

### "Which packages share a connection?" (directory output)

Read `cross_references.package_connection_references` — it maps each package to the connection manager names it references.

---

## Relationship Map

```
envelope
├── content.package_attributes        (package identity)
├── content.variables[]
├── content.connection_managers[] ────────┐
│      referenced by object_name / refId  │
├── content.executables[]  ── recursive via child_executables
│   ├── ExecuteSQLTask.connection ────────┘
│   └── Microsoft.Pipeline
│       └── pipeline
│           ├── components[]
│           │   ├── outputs[].output_columns[].lineage_id ──┐
│           │   └── inputs[].input_columns[].lineage_id ────┤ column lineage
│           ├── paths[]  (output → input wiring) ───────────┘
│           └── topological_order[]
├── precedence constraints  (from_task → to_task = control-flow DAG)
└── completeness_summary
```

---

## Summary

When consuming this JSON:

1. Start with the envelope (`file_type`, `redaction_summary`, `completeness_summary`) to know what you're holding.
2. Use `package_attributes` and the recursive `executables` tree for orientation.
3. Use precedence constraints for control-flow order, `topological_order` for data-flow order.
4. Resolve numeric data types via `data_type_map` and column identity via `lineage_id`.
5. Never treat omitted attributes as errors, and surface `extraction_status: "failed"` entries when present.
