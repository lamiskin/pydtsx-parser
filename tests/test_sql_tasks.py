"""Unit tests for SQL task content extraction.

Tests all requirements from Requirement 8:
- 8.1: Extract SqlStatementSource, Connection, ResultSetType
- 8.2: Extract ParameterBinding elements
- 8.3: SqlCommandVariable fallback
- 8.4: Empty SqlCommandVariable raises ExtractionError
- 8.5: IsStoredProcedure handling
- 8.6: Missing SqlTaskData element detection
"""

import xml.etree.ElementTree as ET

import pytest

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.errors import ExtractionError
from pydtsx_parser.extractors.sql_tasks import (
    extract_sql_task,
    is_sql_task,
)

_DTS_NS = NAMESPACES["DTS"]
_SQLTASK_NS = NAMESPACES["SQLTask"]


def _build_exec_element(
    sql_statement_source: str | None = None,
    connection: str | None = None,
    result_set_type: str | None = None,
    is_stored_procedure: str | None = None,
    sql_command_variable: str | None = None,
    parameter_bindings: list[dict] | None = None,
    include_object_data: bool = True,
    include_sql_task_data: bool = True,
) -> ET.Element:
    """Helper to build a DTS:Executable element with SQLTask:SqlTaskData."""
    exec_elem = ET.Element(f"{{{_DTS_NS}}}Executable")
    exec_elem.set(f"{{{_DTS_NS}}}CreationName", "Microsoft.ExecuteSQLTask")

    if not include_object_data:
        return exec_elem

    object_data = ET.SubElement(exec_elem, f"{{{_DTS_NS}}}ObjectData")

    if not include_sql_task_data:
        return exec_elem

    sql_task_data = ET.SubElement(object_data, f"{{{_SQLTASK_NS}}}SqlTaskData")

    if sql_statement_source is not None:
        sql_task_data.set(f"{{{_SQLTASK_NS}}}SqlStatementSource", sql_statement_source)
    if connection is not None:
        sql_task_data.set(f"{{{_SQLTASK_NS}}}Connection", connection)
    if result_set_type is not None:
        sql_task_data.set(f"{{{_SQLTASK_NS}}}ResultSetType", result_set_type)
    if is_stored_procedure is not None:
        sql_task_data.set(f"{{{_SQLTASK_NS}}}IsStoredProcedure", is_stored_procedure)
    if sql_command_variable is not None:
        sql_task_data.set(f"{{{_SQLTASK_NS}}}SqlCommandVariable", sql_command_variable)

    if parameter_bindings:
        for pb in parameter_bindings:
            pb_elem = ET.SubElement(sql_task_data, f"{{{_SQLTASK_NS}}}ParameterBinding")
            if "parameter_name" in pb:
                pb_elem.set(f"{{{_SQLTASK_NS}}}ParameterName", pb["parameter_name"])
            if "direction" in pb:
                pb_elem.set(f"{{{_SQLTASK_NS}}}ParameterDirection", pb["direction"])
            if "data_type" in pb:
                pb_elem.set(f"{{{_SQLTASK_NS}}}DataType", pb["data_type"])
            if "variable_reference" in pb:
                pb_elem.set(
                    f"{{{_SQLTASK_NS}}}DtsVariableName",
                    pb["variable_reference"],
                )

    return exec_elem


class TestIsSqlTask:
    """Tests for is_sql_task() function."""

    def test_execute_sql_task(self) -> None:
        assert is_sql_task("Microsoft.ExecuteSQLTask") is True

    def test_tsql_execute_task(self) -> None:
        assert is_sql_task("Microsoft.TSQLExecuteTask") is True

    def test_db_maintenance_task(self) -> None:
        assert is_sql_task("Microsoft.DbMaintenanceTSQLExecuteTask") is True

    def test_pipeline_not_sql_task(self) -> None:
        assert is_sql_task("Microsoft.Pipeline") is False

    def test_empty_string(self) -> None:
        assert is_sql_task("") is False

    def test_partial_match(self) -> None:
        """CreationName containing the identifier should match."""
        assert is_sql_task("SSIS.ExecuteSQLTask.3") is True


class TestExtractSqlTask:
    """Tests for extract_sql_task() function."""

    def test_basic_sql_statement_extraction(self) -> None:
        """Requirement 8.1: Extract SQL statement text and connection."""
        exec_elem = _build_exec_element(
            sql_statement_source="SELECT * FROM users",
            connection="{7E0924A9-DC84-4D83-AF5F-33285C19480C}",
        )
        result = extract_sql_task(exec_elem)

        assert result["sql_statement_source"] == "SELECT * FROM users"
        assert result["connection"] == "{7E0924A9-DC84-4D83-AF5F-33285C19480C}"
        assert result["sql_source_type"] == "inline"
        assert result["sql_data_missing"] is False

    def test_result_set_type_extracted(self) -> None:
        """Requirement 8.1: Extract result set type if present."""
        exec_elem = _build_exec_element(
            sql_statement_source="SELECT COUNT(*) FROM orders",
            connection="{CONN-GUID}",
            result_set_type="ResultSetType_SingleRow",
        )
        result = extract_sql_task(exec_elem)

        assert result["result_set_type"] == "ResultSetType_SingleRow"

    def test_result_set_type_omitted_when_absent(self) -> None:
        """Result set type should not be in output when not present in XML."""
        exec_elem = _build_exec_element(
            sql_statement_source="TRUNCATE TABLE foo",
            connection="{CONN-GUID}",
        )
        result = extract_sql_task(exec_elem)

        assert "result_set_type" not in result

    def test_parameter_bindings_extracted(self) -> None:
        """Requirement 8.2: Extract parameter bindings with all fields."""
        bindings = [
            {
                "parameter_name": "0",
                "direction": "Input",
                "data_type": "3",
                "variable_reference": "User::ProjectId",
            },
            {
                "parameter_name": "1",
                "direction": "Output",
                "data_type": "129",
                "variable_reference": "User::ResultName",
            },
        ]
        exec_elem = _build_exec_element(
            sql_statement_source="EXEC sp_GetProject ?, ? OUTPUT",
            connection="{CONN-GUID}",
            parameter_bindings=bindings,
        )
        result = extract_sql_task(exec_elem)

        assert len(result["parameter_bindings"]) == 2
        pb0 = result["parameter_bindings"][0]
        assert pb0["parameter_name"] == "0"
        assert pb0["direction"] == "Input"
        assert pb0["data_type"] == "3"
        assert pb0["variable_reference"] == "User::ProjectId"

        pb1 = result["parameter_bindings"][1]
        assert pb1["parameter_name"] == "1"
        assert pb1["direction"] == "Output"
        assert pb1["data_type"] == "129"
        assert pb1["variable_reference"] == "User::ResultName"

    def test_return_value_parameter_direction(self) -> None:
        """Requirement 8.2: ReturnValue direction is handled."""
        bindings = [
            {
                "parameter_name": "0",
                "direction": "ReturnValue",
                "data_type": "3",
                "variable_reference": "User::ReturnCode",
            },
        ]
        exec_elem = _build_exec_element(
            sql_statement_source="EXEC sp_DoWork",
            connection="{CONN-GUID}",
            parameter_bindings=bindings,
        )
        result = extract_sql_task(exec_elem)

        assert result["parameter_bindings"][0]["direction"] == "ReturnValue"

    def test_no_parameter_bindings(self) -> None:
        """Tasks without parameter bindings return empty list."""
        exec_elem = _build_exec_element(
            sql_statement_source="TRUNCATE TABLE foo",
            connection="{CONN-GUID}",
        )
        result = extract_sql_task(exec_elem)

        assert result["parameter_bindings"] == []

    def test_sql_command_variable_fallback(self) -> None:
        """Requirement 8.3: Use SqlCommandVariable when SqlStatementSource absent."""
        exec_elem = _build_exec_element(
            sql_statement_source="",
            connection="{CONN-GUID}",
            sql_command_variable="User::DynamicSQL",
        )
        result = extract_sql_task(exec_elem)

        assert result["sql_statement_source"] == "User::DynamicSQL"
        assert result["sql_source_type"] == "variable"

    def test_sql_command_variable_when_source_not_set(self) -> None:
        """Requirement 8.3: SqlStatementSource attribute not present at all."""
        exec_elem = _build_exec_element(
            connection="{CONN-GUID}",
            sql_command_variable="User::SqlVar",
        )
        result = extract_sql_task(exec_elem)

        assert result["sql_statement_source"] == "User::SqlVar"
        assert result["sql_source_type"] == "variable"

    def test_empty_sql_command_variable_raises_error(self) -> None:
        """Requirement 8.4: Empty SqlCommandVariable raises ExtractionError."""
        exec_elem = _build_exec_element(
            sql_statement_source="",
            connection="{CONN-GUID}",
            sql_command_variable="   ",
        )
        with pytest.raises(ExtractionError) as exc_info:
            extract_sql_task(exec_elem, file_path="test.dtsx")

        assert "variable reference could not be extracted" in exc_info.value.reason

    def test_is_stored_procedure_true(self) -> None:
        """Requirement 8.5: Extract stored procedure flag when True."""
        exec_elem = _build_exec_element(
            sql_statement_source="sp_GetAllUsers",
            connection="{CONN-GUID}",
            is_stored_procedure="True",
        )
        result = extract_sql_task(exec_elem)

        assert result["is_stored_procedure"] is True
        assert result["sql_statement_source"] == "sp_GetAllUsers"

    def test_is_stored_procedure_false(self) -> None:
        """IsStoredProcedure not set means False."""
        exec_elem = _build_exec_element(
            sql_statement_source="SELECT 1",
            connection="{CONN-GUID}",
        )
        result = extract_sql_task(exec_elem)

        assert result["is_stored_procedure"] is False

    def test_missing_sql_task_data_element(self) -> None:
        """Requirement 8.6: Missing SqlTaskData returns empty structure with flag."""
        exec_elem = _build_exec_element(include_sql_task_data=False)
        result = extract_sql_task(exec_elem)

        assert result["sql_data_missing"] is True
        assert result["sql_statement_source"] == ""
        assert result["connection"] == ""
        assert result["is_stored_procedure"] is False
        assert result["parameter_bindings"] == []

    def test_missing_object_data_element(self) -> None:
        """Missing ObjectData also triggers the missing SqlTaskData path."""
        exec_elem = _build_exec_element(include_object_data=False)
        result = extract_sql_task(exec_elem)

        assert result["sql_data_missing"] is True

    def test_multiline_sql_statement(self) -> None:
        """Multi-statement SQL is preserved as-is."""
        sql = (
            "BEGIN\n"
            "TRUNCATE TABLE [dbo].[MyTable];\n"
            "TRUNCATE TABLE [dbo].[OtherTable];\n"
            "END"
        )
        exec_elem = _build_exec_element(
            sql_statement_source=sql,
            connection="{CONN-GUID}",
        )
        result = extract_sql_task(exec_elem)

        assert result["sql_statement_source"] == sql

    def test_sql_statement_takes_priority_over_variable(self) -> None:
        """When both SqlStatementSource and SqlCommandVariable exist, use inline."""
        exec_elem = _build_exec_element(
            sql_statement_source="SELECT 1",
            connection="{CONN-GUID}",
            sql_command_variable="User::SqlVar",
        )
        result = extract_sql_task(exec_elem)

        assert result["sql_statement_source"] == "SELECT 1"
        assert result["sql_source_type"] == "inline"

    def test_real_world_truncate_sql(self) -> None:
        """Validate against a representative real-world SSIS file pattern."""
        xml_str = (
            f'<DTS:Executable xmlns:DTS="{_DTS_NS}" '
            f'DTS:CreationName="Microsoft.ExecuteSQLTask">'
            f"<DTS:ObjectData>"
            f'<SQLTask:SqlTaskData xmlns:SQLTask="{_SQLTASK_NS}" '
            f'SQLTask:Connection="{{7E0924A9-DC84-4D83-AF5F-33285C19480C}}" '
            f'SQLTask:SqlStatementSource="BEGIN&#xA;TRUNCATE TABLE [dbo].[T1];&#xA;END" />'
            f"</DTS:ObjectData>"
            f"</DTS:Executable>"
        )
        exec_elem = ET.fromstring(xml_str)
        result = extract_sql_task(exec_elem)

        assert "TRUNCATE TABLE [dbo].[T1]" in result["sql_statement_source"]
        assert result["connection"] == "{7E0924A9-DC84-4D83-AF5F-33285C19480C}"
        assert result["sql_data_missing"] is False
