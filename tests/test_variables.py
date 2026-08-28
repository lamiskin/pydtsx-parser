"""Unit tests for variable extraction from SSIS package XML."""

import xml.etree.ElementTree as ET

from pydtsx_parser.extractors.variables import extract_variables

# DTS namespace URI used in test XML
DTS_NS = "www.microsoft.com/SqlServer/Dts"


def _make_package_xml(variables_xml: str = "") -> ET.Element:
    """Build a minimal DTS:Executable element with optional variables XML."""
    xml_str = (
        f'<DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">'
        f"{variables_xml}"
        f"</DTS:Executable>"
    )
    return ET.fromstring(xml_str)


class TestExtractVariablesBasic:
    """Tests for basic variable extraction functionality."""

    def test_no_variables_element_returns_empty_list(self):
        """When no DTS:Variables element exists, return empty list."""
        parent = _make_package_xml("")
        result = extract_variables(parent)
        assert result == []

    def test_empty_variables_element_returns_empty_list(self):
        """When DTS:Variables exists but has no children, return empty list."""
        parent = _make_package_xml("<DTS:Variables/>")
        result = extract_variables(parent)
        assert result == []

    def test_single_string_variable(self):
        """Extract a single string variable with all fields."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="MyVar" DTS:Namespace="User" DTS:DTSID="{ABC}">'
            '<DTS:VariableValue DTS:DataType="8">hello</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert len(result) == 1
        assert result[0]["name"] == "MyVar"
        assert result[0]["namespace"] == "User"
        assert result[0]["data_type"] == "8"
        assert result[0]["value"] == "hello"
        assert result[0]["scope"] == "Package"

    def test_single_integer_variable(self):
        """Extract a variable with numeric data type code 3."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="Counter" DTS:Namespace="User" DTS:DTSID="{DEF}">'
            '<DTS:VariableValue DTS:DataType="3">42</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert len(result) == 1
        assert result[0]["name"] == "Counter"
        assert result[0]["namespace"] == "User"
        assert result[0]["data_type"] == "3"
        assert result[0]["value"] == "42"
        assert result[0]["scope"] == "Package"

    def test_multiple_variables(self):
        """Extract multiple variables from same container."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="Var1" DTS:Namespace="User" DTS:DTSID="{1}">'
            '<DTS:VariableValue DTS:DataType="8">value1</DTS:VariableValue>'
            "</DTS:Variable>"
            '<DTS:Variable DTS:ObjectName="Var2" DTS:Namespace="User" DTS:DTSID="{2}">'
            '<DTS:VariableValue DTS:DataType="11">true</DTS:VariableValue>'
            "</DTS:Variable>"
            '<DTS:Variable DTS:ObjectName="Var3" DTS:Namespace="System" DTS:DTSID="{3}">'
            '<DTS:VariableValue DTS:DataType="3">100</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert len(result) == 3
        assert result[0]["name"] == "Var1"
        assert result[0]["data_type"] == "8"
        assert result[1]["name"] == "Var2"
        assert result[1]["data_type"] == "11"
        assert result[2]["name"] == "Var3"
        assert result[2]["namespace"] == "System"
        assert result[2]["data_type"] == "3"


class TestExtractVariablesScope:
    """Tests for scope handling."""

    def test_default_scope_is_package(self):
        """When no scope is specified, default is 'Package'."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="V" DTS:Namespace="User" DTS:DTSID="{X}">'
            '<DTS:VariableValue DTS:DataType="8">val</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert result[0]["scope"] == "Package"

    def test_custom_scope_task_level(self):
        """When scope is provided, it appears in the output."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="TaskVar" DTS:Namespace="User" DTS:DTSID="{Y}">'
            '<DTS:VariableValue DTS:DataType="130">task_value</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent, scope="MyDataFlowTask")

        assert result[0]["scope"] == "MyDataFlowTask"
        assert result[0]["data_type"] == "130"

    def test_scope_propagates_to_all_variables(self):
        """All variables from same parent get the same scope."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="A" DTS:Namespace="User" DTS:DTSID="{1}">'
            '<DTS:VariableValue DTS:DataType="8">a</DTS:VariableValue>'
            "</DTS:Variable>"
            '<DTS:Variable DTS:ObjectName="B" DTS:Namespace="User" DTS:DTSID="{2}">'
            '<DTS:VariableValue DTS:DataType="8">b</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent, scope="ForEachContainer")

        assert all(v["scope"] == "ForEachContainer" for v in result)


class TestExtractVariablesDataTypes:
    """Tests for data type code extraction."""

    def test_data_type_code_preserved_as_string(self):
        """Data type codes are preserved as raw string values."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="V" DTS:Namespace="User" DTS:DTSID="{A}">'
            '<DTS:VariableValue DTS:DataType="130">text</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert result[0]["data_type"] == "130"

    def test_data_type_boolean(self):
        """Boolean data type code 11 preserved."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="Flag" DTS:Namespace="User" DTS:DTSID="{B}">'
            '<DTS:VariableValue DTS:DataType="11">0</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert result[0]["data_type"] == "11"
        assert result[0]["value"] == "0"

    def test_data_type_bstr(self):
        """BSTR data type code 8 preserved."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="V" DTS:Namespace="User" DTS:DTSID="{C}">'
            '<DTS:VariableValue DTS:DataType="8">hello</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert result[0]["data_type"] == "8"


class TestExtractVariablesEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_variable_with_empty_value(self):
        """Variable with empty text content returns empty string value."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="EmptyVar" DTS:Namespace="User" DTS:DTSID="{E}">'
            '<DTS:VariableValue DTS:DataType="8"></DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert result[0]["value"] == ""

    def test_variable_with_self_closing_value(self):
        """Variable with self-closing VariableValue returns empty value."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="SelfClose" DTS:Namespace="User" DTS:DTSID="{SC}">'
            '<DTS:VariableValue DTS:DataType="8"/>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert result[0]["value"] == ""
        assert result[0]["data_type"] == "8"

    def test_variable_with_no_variable_value_element(self):
        """Variable missing VariableValue child has empty data_type and value."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="NoValue" DTS:Namespace="User" DTS:DTSID="{F}">'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert result[0]["name"] == "NoValue"
        assert result[0]["data_type"] == ""
        assert result[0]["value"] == ""

    def test_variable_with_multiline_value(self):
        """Variable with multiline text content preserves newlines."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="SqlVar" DTS:Namespace="User" DTS:DTSID="{G}">'
            '<DTS:VariableValue DTS:DataType="8">SELECT *\nFROM table\nWHERE id = 1</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert "SELECT *" in result[0]["value"]
        assert "FROM table" in result[0]["value"]

    def test_variable_missing_namespace_attribute(self):
        """Variable with no Namespace attribute returns empty namespace."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="NoNS" DTS:DTSID="{H}">'
            '<DTS:VariableValue DTS:DataType="3">0</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert result[0]["namespace"] == ""

    def test_variable_missing_object_name(self):
        """Variable with no ObjectName attribute returns empty name."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:Namespace="User" DTS:DTSID="{I}">'
            '<DTS:VariableValue DTS:DataType="3">0</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert result[0]["name"] == ""

    def test_output_keys_present(self):
        """Each variable dict has exactly the expected keys."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="V" DTS:Namespace="User" DTS:DTSID="{J}">'
            '<DTS:VariableValue DTS:DataType="3">1</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        expected_keys = {"name", "namespace", "data_type", "value", "scope"}
        assert set(result[0].keys()) == expected_keys

    def test_variable_with_special_characters_in_value(self):
        """Variable value with XML-special characters is preserved."""
        variables_xml = (
            "<DTS:Variables>"
            '<DTS:Variable DTS:ObjectName="Special" DTS:Namespace="User" DTS:DTSID="{K}">'
            '<DTS:VariableValue DTS:DataType="8">&lt;tag&gt; &amp; "quotes"</DTS:VariableValue>'
            "</DTS:Variable>"
            "</DTS:Variables>"
        )
        parent = _make_package_xml(variables_xml)
        result = extract_variables(parent)

        assert result[0]["value"] == '<tag> & "quotes"'
