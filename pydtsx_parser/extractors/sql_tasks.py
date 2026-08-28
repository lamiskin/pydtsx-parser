"""SQL task content extraction from SSIS executables.

Extracts Execute SQL Task data from DTS:Executable elements whose CreationName
contains "DbMaintenanceTSQLExecuteTask", "ExecuteSQLTask", or "TSQLExecuteTask".

For each matching executable, extracts:
- SQL statement text (SqlStatementSource attribute)
- Connection reference (Connection attribute)
- Result set type (ResultSetType attribute)
- Parameter bindings (ParameterBinding elements with name, direction, data type, variable)
- SqlCommandVariable fallback when SqlStatementSource is absent/empty
- Stored procedure detection (IsStoredProcedure attribute)
- Missing SqlTaskData element detection
"""

import xml.etree.ElementTree as ET

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.errors import ExtractionError

_DTS_NS = NAMESPACES["DTS"]
_SQLTASK_NS = NAMESPACES["SQLTask"]

# CreationName substrings that identify SQL task executables
SQL_TASK_CREATION_NAMES = (
    "DbMaintenanceTSQLExecuteTask",
    "ExecuteSQLTask",
    "TSQLExecuteTask",
)


def is_sql_task(creation_name: str) -> bool:
    """Determine if an executable is a SQL task based on its CreationName.

    Checks if the CreationName contains any of the known SQL task identifiers.

    Args:
        creation_name: The CreationName attribute value of an executable.

    Returns:
        True if the executable is a SQL task, False otherwise.
    """
    if not creation_name:
        return False
    return any(name in creation_name for name in SQL_TASK_CREATION_NAMES)


def extract_sql_task(exec_elem: ET.Element, file_path: str = "") -> dict:
    """Extract SQL task data from a DTS:Executable element.

    Locates the SQLTask:SqlTaskData element within the executable's ObjectData
    and extracts the SQL statement source, connection reference, result set type,
    parameter bindings, and stored procedure flag.

    If SqlStatementSource is empty/absent and SqlCommandVariable is present,
    uses the variable reference as the SQL source. If the variable reference
    cannot be extracted (empty value), raises ExtractionError.

    If the SQLTask:SqlTaskData element is missing entirely, returns a dict
    with an empty SQL content structure and a flag indicating the missing element.

    Args:
        exec_elem: A DTS:Executable XML element identified as a SQL task.
        file_path: Source file path for error reporting.

    Returns:
        Dictionary with SQL task data including:
        - sql_statement_source: The SQL text or variable reference
        - connection: The connection manager reference
        - result_set_type: The result set type (if present)
        - is_stored_procedure: Boolean flag for stored procedure tasks
        - parameter_bindings: List of parameter binding dicts
        - sql_data_missing: Flag indicating SqlTaskData element was not found

    Raises:
        ExtractionError: If SqlStatementSource is empty/absent, SqlCommandVariable
            is present but has an empty or unresolvable value.
    """
    # Find the ObjectData container
    object_data = exec_elem.find(f"{{{_DTS_NS}}}ObjectData")
    if object_data is None:
        return _build_missing_sql_data_result()

    # Find the SQLTask:SqlTaskData element
    sql_task_data = object_data.find(f"{{{_SQLTASK_NS}}}SqlTaskData")
    if sql_task_data is None:
        return _build_missing_sql_data_result()

    # Extract attributes from SqlTaskData
    connection = sql_task_data.get(f"{{{_SQLTASK_NS}}}Connection", "")
    sql_statement_source = sql_task_data.get(f"{{{_SQLTASK_NS}}}SqlStatementSource", "")
    result_set_type = sql_task_data.get(f"{{{_SQLTASK_NS}}}ResultSetType")
    is_stored_procedure_str = sql_task_data.get(
        f"{{{_SQLTASK_NS}}}IsStoredProcedure", ""
    )
    sql_command_variable = sql_task_data.get(f"{{{_SQLTASK_NS}}}SqlCommandVariable", "")

    # Determine stored procedure flag
    is_stored_procedure = is_stored_procedure_str.lower() == "true"

    # Handle SQL source: inline statement vs variable reference
    # Requirement 8.3: If SqlStatementSource is empty/absent and SqlCommandVariable
    # is present, use the variable name as the SQL source
    if not sql_statement_source and sql_command_variable:
        # Requirement 8.4: If the variable reference is empty, fail entirely
        if not sql_command_variable.strip():
            raise ExtractionError(
                file_path,
                "SQL task has empty SqlStatementSource and SqlCommandVariable "
                "attribute is present but the variable reference could not be "
                "extracted (empty value)",
            )
        sql_source = sql_command_variable
        sql_source_type = "variable"
    else:
        sql_source = sql_statement_source
        sql_source_type = "inline"

    # Extract parameter bindings
    parameter_bindings = _extract_parameter_bindings(sql_task_data)

    # Build result
    result: dict = {
        "sql_statement_source": sql_source,
        "sql_source_type": sql_source_type,
        "connection": connection,
        "is_stored_procedure": is_stored_procedure,
        "parameter_bindings": parameter_bindings,
        "sql_data_missing": False,
    }

    # Only include result_set_type if present (omit optional absent attributes)
    if result_set_type is not None:
        result["result_set_type"] = result_set_type

    return result


def _build_missing_sql_data_result() -> dict:
    """Build the result dict for when SqlTaskData element is missing.

    Requirement 8.6: Include the task with an empty SQL content structure
    and a flag indicating the SQL data element was missing.

    Returns:
        Dictionary with empty SQL content and sql_data_missing=True.
    """
    return {
        "sql_statement_source": "",
        "sql_source_type": "inline",
        "connection": "",
        "is_stored_procedure": False,
        "parameter_bindings": [],
        "sql_data_missing": True,
    }


def _extract_parameter_bindings(sql_task_data: ET.Element) -> list[dict]:
    """Extract ParameterBinding elements from SqlTaskData.

    Each ParameterBinding has attributes for parameter name, direction,
    data type, and variable reference.

    Args:
        sql_task_data: The SQLTask:SqlTaskData XML element.

    Returns:
        List of parameter binding dicts with name, direction, data_type,
        and variable_reference keys. Returns empty list if no bindings exist.
    """
    bindings = []

    # ParameterBinding elements are children of SqlTaskData in the SQLTask namespace
    for binding_elem in sql_task_data.findall(f"{{{_SQLTASK_NS}}}ParameterBinding"):
        binding: dict = {}

        parameter_name = binding_elem.get(f"{{{_SQLTASK_NS}}}ParameterName", "")
        if parameter_name:
            binding["parameter_name"] = parameter_name

        direction = binding_elem.get(f"{{{_SQLTASK_NS}}}ParameterDirection", "")
        if direction:
            binding["direction"] = direction

        data_type = binding_elem.get(f"{{{_SQLTASK_NS}}}DataType", "")
        if data_type:
            binding["data_type"] = data_type

        variable_reference = binding_elem.get(f"{{{_SQLTASK_NS}}}DtsVariableName", "")
        if variable_reference:
            binding["variable_reference"] = variable_reference

        bindings.append(binding)

    return bindings
