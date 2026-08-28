"""MCP server exposing the parser as tools for MCP-compatible clients.

Provides tools for parsing SSIS packages, extracting SQL, tracing data
lineage, and exploring package structure.
"""

import json
import xml.etree.ElementTree as ET

from mcp.server.fastmcp import FastMCP

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.dispatcher import dispatch
from pydtsx_parser.extractors.pipeline import extract_pipeline
from pydtsx_parser.extractors.precedence import extract_precedence_constraints
from pydtsx_parser.extractors.sql_tasks import extract_sql_task, is_sql_task
from pydtsx_parser.parsers.dtsx import parse_dtsx
from pydtsx_parser.redaction import redact
from pydtsx_parser.xml_utils import get_root, parse_xml

_DTS_NS = NAMESPACES["DTS"]

mcp = FastMCP(
    "pydtsx-parser",
    instructions=(
        "Parse SQL Server Integration Services .dtsx package files into "
        "structured JSON. Use these tools to extract SQL, data lineage, "
        "control flow, data flow pipelines, and connection managers from "
        "SSIS packages."
    ),
)


@mcp.tool()
def parse_dtsx_file(file_path: str, pretty: bool = True) -> str:
    """Parse a single SSIS file (.dtsx, .dtproj, .conmgr, .params) and return structured JSON.

    Args:
        file_path: Absolute path to the SSIS file to parse.
        pretty: Whether to pretty-print the JSON output (default True).

    Returns:
        JSON string of the fully parsed file with envelope metadata,
        or an error message if parsing fails.
    """
    try:
        result = dispatch(file_path)
        indent = 2 if pretty else None
        return json.dumps(result, indent=indent, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": True, "message": str(e)}, indent=2)


@mcp.tool()
def parse_ssis_directory(directory_path: str, pretty: bool = True) -> str:
    """Parse all SSIS files in a directory recursively.

    Discovers .dtsx, .dtproj, .conmgr, and .params files, parses each,
    and returns a combined project-level output with cross-references.

    Args:
        directory_path: Root directory to scan for SSIS files.
        pretty: Whether to pretty-print the JSON output (default True).

    Returns:
        JSON string with combined project output including packages,
        connection managers, parameters, projects, and cross-references.
    """
    try:
        result = dispatch(directory_path)
        indent = 2 if pretty else None
        return json.dumps(result, indent=indent, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": True, "message": str(e)}, indent=2)


@mcp.tool()
def get_package_summary(file_path: str) -> str:
    """Get a high-level summary of an SSIS package without the full JSON dump.

    Returns package name, task counts by type, control flow structure,
    data flow component counts, connection managers, and variable counts.
    This is the best first tool to call to understand what a package does.

    Args:
        file_path: Absolute path to the .dtsx file.

    Returns:
        JSON summary with package overview, task breakdown, data flow info,
        and connection details.
    """
    try:
        parsed = parse_dtsx(file_path)
        tree = parse_xml(file_path)
        root = get_root(tree, file_path)

        # Package identity
        pkg_attrs = parsed.get("package_attributes", {})
        summary = {
            "package_name": pkg_attrs.get("object_name", ""),
            "creation_name": pkg_attrs.get("creation_name", ""),
            "last_modified_version": pkg_attrs.get("last_modified_product_version", ""),
        }

        # Connection managers
        conn_mgrs = parsed.get("connection_managers", [])
        summary["connection_managers"] = [
            {
                "name": cm.get("object_name", ""),
                "type": cm.get("creation_name", ""),
            }
            for cm in conn_mgrs
        ]

        # Variables
        variables = parsed.get("variables", [])
        summary["variable_count"] = len(variables)
        summary["variables"] = [
            {"name": v.get("name", ""), "namespace": v.get("namespace", "")}
            for v in variables[:20]  # Cap at 20 for readability
        ]

        # Executables breakdown
        executables = parsed.get("executables", [])
        task_types: dict[str, int] = {}
        pipeline_tasks: list[dict] = []
        sql_tasks_list: list[dict] = []
        _categorize_executables(executables, task_types, pipeline_tasks, sql_tasks_list)

        summary["task_counts"] = task_types
        summary["total_tasks"] = sum(task_types.values())

        # Data flow summary
        data_flows = []
        for pipe_exec in pipeline_tasks:
            pipe_tree_elem = _find_executable_in_tree(root, pipe_exec.get("ref_id", ""))
            if pipe_tree_elem is not None:
                df = extract_pipeline(pipe_tree_elem)
                components = df.get("components", [])
                sources = [c for c in components if c.get("classification") == "source"]
                destinations = [
                    c for c in components if c.get("classification") == "destination"
                ]
                transforms = [
                    c for c in components if c.get("classification") == "transformation"
                ]
                data_flows.append(
                    {
                        "task_name": pipe_exec.get("object_name", ""),
                        "source_count": len(sources),
                        "destination_count": len(destinations),
                        "transformation_count": len(transforms),
                        "total_components": len(components),
                        "topological_order": df.get("topological_order", []),
                    }
                )

        summary["data_flows"] = data_flows

        # SQL tasks summary
        summary["sql_tasks"] = [
            {
                "task_name": t.get("object_name", ""),
                "ref_id": t.get("ref_id", ""),
            }
            for t in sql_tasks_list
        ]

        # Precedence constraints
        constraints = extract_precedence_constraints(root, file_path)
        summary["precedence_constraint_count"] = len(constraints)

        # Completeness
        summary["completeness"] = parsed.get("completeness_summary", {})

        return json.dumps(summary, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": True, "message": str(e)}, indent=2)


@mcp.tool()
def get_sql_code(file_path: str, task_name: str | None = None) -> str:
    """Extract SQL code from an SSIS package.

    Returns all SQL statements found in Execute SQL Tasks and OLE DB source
    components. If task_name is provided, filters to that specific task.

    Args:
        file_path: Absolute path to the .dtsx file.
        task_name: Optional task ObjectName to filter to a specific task.

    Returns:
        JSON with extracted SQL statements and their containing tasks.
    """
    try:
        tree = parse_xml(file_path)
        root = get_root(tree, file_path)

        sql_results = []

        # Find SQL tasks
        for elem in root.iter(f"{{{_DTS_NS}}}Executable"):
            creation_name = elem.get(f"{{{_DTS_NS}}}CreationName", "")
            object_name = elem.get(f"{{{_DTS_NS}}}ObjectName", "")

            if task_name and object_name != task_name:
                continue

            if is_sql_task(creation_name):
                sql_data = extract_sql_task(elem, file_path)
                sql_results.append(
                    {
                        "task_name": object_name,
                        "task_type": creation_name,
                        "sql_statement": sql_data.get("sql_statement_source", ""),
                        "sql_source_type": sql_data.get("sql_source_type", ""),
                        "connection": sql_data.get("connection", ""),
                        "is_stored_procedure": sql_data.get(
                            "is_stored_procedure", False
                        ),
                        "parameter_bindings": sql_data.get("parameter_bindings", []),
                    }
                )

        # Find SQL in OLE DB source components within pipelines
        for pipe_elem in root.iter(f"{{{_DTS_NS}}}Executable"):
            creation_name = pipe_elem.get(f"{{{_DTS_NS}}}CreationName", "")
            pipe_name = pipe_elem.get(f"{{{_DTS_NS}}}ObjectName", "")

            if creation_name != "Microsoft.Pipeline":
                continue
            if task_name and pipe_name != task_name:
                continue

            df = extract_pipeline(pipe_elem)
            for comp in df.get("components", []):
                class_id = comp.get("component_class_id", "")
                if "Source" in class_id or "OLEDBSource" in class_id:
                    custom_props = comp.get("custom_properties", [])
                    sql_cmd = next(
                        (
                            p.get("value", "")
                            for p in custom_props
                            if p.get("name") == "SqlCommand"
                        ),
                        "",
                    )
                    open_rowset = next(
                        (
                            p.get("value", "")
                            for p in custom_props
                            if p.get("name") == "OpenRowset"
                        ),
                        "",
                    )
                    if sql_cmd or open_rowset:
                        sql_results.append(
                            {
                                "task_name": pipe_name,
                                "component_name": comp.get("name", ""),
                                "task_type": "DataFlowSource",
                                "sql_statement": sql_cmd or open_rowset,
                                "sql_source_type": "sql_command"
                                if sql_cmd
                                else "table_or_view",
                            }
                        )

        return json.dumps(
            {"sql_statements": sql_results, "count": len(sql_results)},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"error": True, "message": str(e)}, indent=2)


@mcp.tool()
def get_data_lineage(file_path: str, task_name: str | None = None) -> str:
    """Trace data lineage in an SSIS package.

    Shows execution order (precedence constraints) and for each data flow task,
    what data sources feed into what destinations through which transformations.

    Args:
        file_path: Absolute path to the .dtsx file.
        task_name: Optional task name to trace lineage for a specific data flow.

    Returns:
        JSON with control flow order and data lineage per data flow task.
    """
    try:
        tree = parse_xml(file_path)
        root = get_root(tree, file_path)

        # Control flow: precedence constraints
        constraints = extract_precedence_constraints(root, file_path)
        control_flow = [
            {
                "from": c.get("from_task", "").rsplit("\\", 1)[-1],
                "to": c.get("to_task", "").rsplit("\\", 1)[-1],
                "condition": c.get("value", "Success"),
                "eval_op": c.get("eval_op", "Constraint"),
            }
            for c in constraints
        ]

        # Data flow lineage
        data_flow_lineage = []
        for pipe_elem in root.iter(f"{{{_DTS_NS}}}Executable"):
            creation_name = pipe_elem.get(f"{{{_DTS_NS}}}CreationName", "")
            pipe_name = pipe_elem.get(f"{{{_DTS_NS}}}ObjectName", "")

            if creation_name != "Microsoft.Pipeline":
                continue
            if task_name and pipe_name != task_name:
                continue

            df = extract_pipeline(pipe_elem)
            components = df.get("components", [])

            sources = []
            destinations = []
            transformations = []

            for comp in components:
                classification = comp.get("classification", "unknown")
                entry = {
                    "name": comp.get("name", ""),
                    "class_id": comp.get("component_class_id", ""),
                }

                if classification == "source":
                    # Get source details
                    custom_props = comp.get("custom_properties", [])
                    sql_cmd = next(
                        (
                            p.get("value", "")
                            for p in custom_props
                            if p.get("name") == "SqlCommand"
                        ),
                        "",
                    )
                    open_rowset = next(
                        (
                            p.get("value", "")
                            for p in custom_props
                            if p.get("name") == "OpenRowset"
                        ),
                        "",
                    )
                    entry["query_or_table"] = sql_cmd or open_rowset or ""

                    # Count output columns
                    for output in comp.get("outputs", []):
                        if not output.get("is_error_out", False):
                            entry["output_column_count"] = len(
                                output.get("output_columns", [])
                            )
                            break
                    sources.append(entry)

                elif classification == "destination":
                    # Count input columns
                    for inp in comp.get("inputs", []):
                        entry["input_column_count"] = len(inp.get("input_columns", []))
                        break
                    destinations.append(entry)

                elif classification == "transformation":
                    entry["type"] = comp.get("component_class_id", "").replace(
                        "Microsoft.", ""
                    )
                    transformations.append(entry)

            data_flow_lineage.append(
                {
                    "task_name": pipe_name,
                    "topological_order": df.get("topological_order", []),
                    "sources": sources,
                    "transformations": transformations,
                    "destinations": destinations,
                    "path_count": len(df.get("paths", [])),
                }
            )

        return json.dumps(
            {
                "control_flow_edges": control_flow,
                "data_flow_lineage": data_flow_lineage,
            },
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"error": True, "message": str(e)}, indent=2)


@mcp.tool()
def get_data_flows(file_path: str, task_name: str | None = None) -> str:
    """Extract all Data Flow Task pipeline definitions from an SSIS package.

    Returns the full data flow pipeline definitions including all components
    with their classification, custom properties, column counts, and paths.

    Args:
        file_path: Absolute path to the .dtsx file.
        task_name: Optional task name to get a specific data flow only.

    Returns:
        JSON with all data flow definitions including components and paths.
    """
    try:
        tree = parse_xml(file_path)
        root = get_root(tree, file_path)

        data_flows = []

        for pipe_elem in root.iter(f"{{{_DTS_NS}}}Executable"):
            creation_name = pipe_elem.get(f"{{{_DTS_NS}}}CreationName", "")
            pipe_name = pipe_elem.get(f"{{{_DTS_NS}}}ObjectName", "")

            if creation_name != "Microsoft.Pipeline":
                continue
            if task_name and pipe_name != task_name:
                continue

            df = extract_pipeline(pipe_elem)

            # Redact sensitive values
            redacted_df, _ = redact(df)

            data_flows.append(
                {
                    "task_name": pipe_name,
                    "components": redacted_df.get("components", []),
                    "paths": redacted_df.get("paths", []),
                    "topological_order": redacted_df.get("topological_order", []),
                    "error_outputs": redacted_df.get("error_outputs", []),
                }
            )

        return json.dumps(
            {"data_flows": data_flows, "count": len(data_flows)},
            indent=2,
            ensure_ascii=False,
        )

    except Exception as e:
        return json.dumps({"error": True, "message": str(e)}, indent=2)


# --- Helpers ---


def _categorize_executables(
    executables: list[dict],
    task_types: dict,
    pipeline_tasks: list,
    sql_tasks_list: list,
) -> None:
    """Recursively categorize executables by type."""
    for exe in executables:
        creation_name = exe.get("creation_name", "")
        # Simplify the name for display
        simple_name = creation_name.replace("Microsoft.", "").replace("STOCK:", "")
        task_types[simple_name] = task_types.get(simple_name, 0) + 1

        if creation_name == "Microsoft.Pipeline":
            pipeline_tasks.append(exe)
        if is_sql_task(creation_name):
            sql_tasks_list.append(exe)

        # Recurse into children
        children = exe.get("child_executables", [])
        if children:
            _categorize_executables(
                children, task_types, pipeline_tasks, sql_tasks_list
            )


def _find_executable_in_tree(root: ET.Element, ref_id: str) -> ET.Element | None:
    """Find an executable element in the XML tree by its refId."""
    for elem in root.iter(f"{{{_DTS_NS}}}Executable"):
        if elem.get(f"{{{_DTS_NS}}}refId") == ref_id:
            return elem
    return None


def main() -> None:
    """Console-script entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
