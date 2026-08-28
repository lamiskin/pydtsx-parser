"""Unit tests for edge cases and error conditions.

Validates error handling across all parser modules:
- Null/empty file paths (Req 1.9)
- File not found (Req 1.7)
- Malformed XML (Req 1.6)
- File-not-found precedence over malformed XML (Req 1.10)
- Missing ObjectName on connection manager (Req 3.7)
- Missing required dtproj elements (Req 4.7)
- Empty params file (Req 5.2)
- Malformed params XML (Req 5.3)
- Empty constraints (Req 9.5)
- Malformed constraint data (Req 9.6)
- Empty transformations (Req 10.6)
- SQL task missing SqlTaskData (Req 8.6)
- SqlCommandVariable with empty value (Req 8.4)
- Failed derived column overwrite extraction (Req 10.7)
"""

import xml.etree.ElementTree as ET

import pytest

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.errors import ExtractionError, FileNotFoundError, MalformedXMLError
from pydtsx_parser.extractors.components import extract_component
from pydtsx_parser.extractors.connections import extract_single_connection_manager
from pydtsx_parser.extractors.precedence import extract_precedence_constraints
from pydtsx_parser.extractors.sql_tasks import extract_sql_task
from pydtsx_parser.parsers.dtproj import parse_dtproj
from pydtsx_parser.parsers.dtsx import parse_dtsx
from pydtsx_parser.parsers.params import parse_params

DTS_NS = NAMESPACES["DTS"]
SSIS_NS = NAMESPACES["SSIS"]
SQLTASK_NS = NAMESPACES["SQLTask"]


# =============================================================================
# 1. Null/empty file path (Req 1.9)
# =============================================================================


class TestNullEmptyFilePath:
    """parse_dtsx raises FileNotFoundError for null or empty file paths."""

    def test_empty_string_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_dtsx("")

    def test_none_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_dtsx(None)


# =============================================================================
# 2. File not found (Req 1.7)
# =============================================================================


class TestFileNotFound:
    """parse_dtsx raises FileNotFoundError for non-existent paths."""

    def test_nonexistent_path_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError) as exc_info:
            parse_dtsx("/nonexistent/path/to/file.dtsx")
        assert "/nonexistent/path/to/file.dtsx" in str(exc_info.value)


# =============================================================================
# 3. Malformed XML (Req 1.6)
# =============================================================================


class TestMalformedXML:
    """parse_dtsx raises MalformedXMLError with file path and details."""

    def test_broken_xml_raises_malformed_error(self, tmp_path):
        broken_file = tmp_path / "broken.dtsx"
        broken_file.write_text("<DTS:Executable><unclosed", encoding="utf-8")

        with pytest.raises(MalformedXMLError) as exc_info:
            parse_dtsx(str(broken_file))

        assert str(broken_file) in exc_info.value.file_path
        assert exc_info.value.reason  # Contains XML parser details

    def test_invalid_xml_encoding_raises_malformed_error(self, tmp_path):
        invalid_file = tmp_path / "invalid.dtsx"
        invalid_file.write_bytes(
            b"<?xml version='1.0' encoding='utf-8'?>\n<root>\xff\xfe</root>"
        )

        with pytest.raises(MalformedXMLError) as exc_info:
            parse_dtsx(str(invalid_file))

        assert exc_info.value.file_path == str(invalid_file)


# =============================================================================
# 4. File-not-found takes precedence over malformed XML (Req 1.10)
# =============================================================================


class TestErrorPrecedence:
    """File-not-found takes precedence regardless of what content would be."""

    def test_nonexistent_file_returns_file_not_found_not_malformed(self):
        # Even though this path would contain broken XML if it existed,
        # the error should be FileNotFoundError not MalformedXMLError
        with pytest.raises(FileNotFoundError):
            parse_dtsx("/this/does/not/exist/broken.dtsx")

    def test_empty_path_takes_precedence(self):
        # Empty path should be FileNotFoundError, never MalformedXMLError
        with pytest.raises(FileNotFoundError):
            parse_dtsx("")


# =============================================================================
# 5. Missing ObjectName on connection manager (Req 3.7)
# =============================================================================


class TestMissingObjectName:
    """extract_single_connection_manager raises ExtractionError if ObjectName missing."""

    def test_missing_object_name_raises_extraction_error(self):
        xml = f"""<DTS:ConnectionManager xmlns:DTS="{DTS_NS}"
            DTS:refId="Package.ConnectionManagers[Test]"
            DTS:DTSID="{{12345}}"
            DTS:CreationName="OLEDB">
            <DTS:ObjectData>
                <DTS:ConnectionManager>
                    <DTS:Property DTS:Name="ConnectionString">Server=test</DTS:Property>
                </DTS:ConnectionManager>
            </DTS:ObjectData>
        </DTS:ConnectionManager>"""

        element = ET.fromstring(xml)

        with pytest.raises(ExtractionError) as exc_info:
            extract_single_connection_manager(element, "test.dtsx")

        assert "ObjectName" in exc_info.value.reason

    def test_connection_manager_with_object_name_succeeds(self):
        xml = f"""<DTS:ConnectionManager xmlns:DTS="{DTS_NS}"
            DTS:refId="Package.ConnectionManagers[Test]"
            DTS:ObjectName="TestConn"
            DTS:DTSID="{{12345}}"
            DTS:CreationName="OLEDB">
            <DTS:ObjectData>
                <DTS:ConnectionManager>
                    <DTS:Property DTS:Name="ConnectionString">Server=test</DTS:Property>
                </DTS:ConnectionManager>
            </DTS:ObjectData>
        </DTS:ConnectionManager>"""

        element = ET.fromstring(xml)
        result = extract_single_connection_manager(element, "test.dtsx")
        assert result["object_name"] == "TestConn"


# =============================================================================
# 6. Missing required dtproj elements (Req 4.7)
# =============================================================================


class TestMissingDtprojElements:
    """parse_dtproj returns error dict for missing DeploymentModel/ProductVersion/SchemaVersion."""

    def test_missing_deployment_model(self, tmp_path):
        xml = """<?xml version="1.0"?>
<Project>
  <ProductVersion>15.0.2000.180</ProductVersion>
  <SchemaVersion>9.0.1.0</SchemaVersion>
</Project>"""
        dtproj_file = tmp_path / "test.dtproj"
        dtproj_file.write_text(xml, encoding="utf-8")

        result = parse_dtproj(str(dtproj_file))
        assert result["error"] is True
        assert "DeploymentModel" in result["message"]

    def test_missing_product_version(self, tmp_path):
        xml = """<?xml version="1.0"?>
<Project>
  <DeploymentModel>Project</DeploymentModel>
  <SchemaVersion>9.0.1.0</SchemaVersion>
</Project>"""
        dtproj_file = tmp_path / "test.dtproj"
        dtproj_file.write_text(xml, encoding="utf-8")

        result = parse_dtproj(str(dtproj_file))
        assert result["error"] is True
        assert "ProductVersion" in result["message"]

    def test_missing_schema_version(self, tmp_path):
        xml = """<?xml version="1.0"?>
<Project>
  <DeploymentModel>Project</DeploymentModel>
  <ProductVersion>15.0.2000.180</ProductVersion>
</Project>"""
        dtproj_file = tmp_path / "test.dtproj"
        dtproj_file.write_text(xml, encoding="utf-8")

        result = parse_dtproj(str(dtproj_file))
        assert result["error"] is True
        assert "SchemaVersion" in result["message"]

    def test_missing_all_required_elements(self, tmp_path):
        xml = """<?xml version="1.0"?>
<Project>
  <SomeOtherElement>value</SomeOtherElement>
</Project>"""
        dtproj_file = tmp_path / "test.dtproj"
        dtproj_file.write_text(xml, encoding="utf-8")

        result = parse_dtproj(str(dtproj_file))
        assert result["error"] is True
        assert "DeploymentModel" in result["message"]
        assert "ProductVersion" in result["message"]
        assert "SchemaVersion" in result["message"]


# =============================================================================
# 7. Empty params file (Req 5.2)
# =============================================================================


class TestEmptyParamsFile:
    """parse_params with empty SSIS:Parameters returns empty list."""

    def test_self_closing_parameters_returns_empty_list(self, tmp_path):
        xml = f"""<?xml version="1.0"?>
<SSIS:Parameters xmlns:SSIS="{SSIS_NS}" />"""
        params_file = tmp_path / "Project.params"
        params_file.write_text(xml, encoding="utf-8")

        result = parse_params(str(params_file))
        assert result["parameters"] == []

    def test_empty_parameters_element_returns_empty_list(self, tmp_path):
        xml = f"""<?xml version="1.0"?>
<SSIS:Parameters xmlns:SSIS="{SSIS_NS}">
</SSIS:Parameters>"""
        params_file = tmp_path / "Project.params"
        params_file.write_text(xml, encoding="utf-8")

        result = parse_params(str(params_file))
        assert result["parameters"] == []


# =============================================================================
# 8. Malformed params XML (Req 5.3)
# =============================================================================


class TestMalformedParamsXML:
    """parse_params with malformed XML raises MalformedXMLError."""

    def test_broken_params_xml_raises_malformed_error(self, tmp_path):
        params_file = tmp_path / "Project.params"
        params_file.write_text("<SSIS:Parameters><unclosed", encoding="utf-8")

        with pytest.raises(MalformedXMLError) as exc_info:
            parse_params(str(params_file))

        assert str(params_file) in exc_info.value.file_path


# =============================================================================
# 9. Empty constraints (Req 9.5)
# =============================================================================


class TestEmptyConstraints:
    """Package with no DTS:PrecedenceConstraints returns empty list."""

    def test_no_precedence_constraints_element_returns_empty(self):
        xml = f"""<DTS:Executable xmlns:DTS="{DTS_NS}"
            DTS:refId="Package"
            DTS:ObjectName="Package">
        </DTS:Executable>"""

        element = ET.fromstring(xml)
        result = extract_precedence_constraints(element, "test.dtsx")
        assert result == []

    def test_empty_precedence_constraints_element_returns_empty(self):
        xml = f"""<DTS:Executable xmlns:DTS="{DTS_NS}"
            DTS:refId="Package"
            DTS:ObjectName="Package">
            <DTS:PrecedenceConstraints />
        </DTS:Executable>"""

        element = ET.fromstring(xml)
        result = extract_precedence_constraints(element, "test.dtsx")
        assert result == []


# =============================================================================
# 10. Empty transformations (Req 10.6)
# =============================================================================


class TestEmptyTransformations:
    """DerivedColumn/Sort/MergeJoin with no configured columns returns empty transformation list."""

    def test_derived_column_with_no_columns_returns_empty_list(self):
        xml = """<component refId="Package\\Task\\DC"
            name="Derived Column"
            componentClassID="Microsoft.DerivedColumn">
            <outputs>
                <output refId="Package\\Task\\DC.Outputs[Output]"
                    name="Derived Column Output">
                </output>
            </outputs>
            <inputs>
                <input refId="Package\\Task\\DC.Inputs[Input]"
                    name="Derived Column Input">
                </input>
            </inputs>
        </component>"""

        element = ET.fromstring(xml)
        result = extract_component(element)
        assert result["derived_columns"] == []
        assert result["classification"] == "transformation"

    def test_sort_with_no_sort_columns_returns_empty_list(self):
        xml = """<component refId="Package\\Task\\Sort"
            name="Sort"
            componentClassID="Microsoft.Sort">
            <outputs>
                <output refId="Package\\Task\\Sort.Outputs[Output]"
                    name="Sort Output">
                </output>
            </outputs>
        </component>"""

        element = ET.fromstring(xml)
        result = extract_component(element)
        assert result["sort_columns"] == []
        assert result["classification"] == "transformation"

    def test_merge_join_with_no_configured_columns_returns_empty(self):
        xml = """<component refId="Package\\Task\\MJ"
            name="Merge Join"
            componentClassID="Microsoft.MergeJoin">
            <properties>
                <property name="JoinType">1</property>
                <property name="TreatNullsAsEqual">0</property>
            </properties>
            <inputs>
                <input refId="Package\\Task\\MJ.Inputs[Left]"
                    name="Merge Join Left Input">
                </input>
                <input refId="Package\\Task\\MJ.Inputs[Right]"
                    name="Merge Join Right Input">
                </input>
            </inputs>
            <outputs>
                <output refId="Package\\Task\\MJ.Outputs[Output]"
                    name="Merge Join Output">
                </output>
            </outputs>
        </component>"""

        element = ET.fromstring(xml)
        result = extract_component(element)
        assert result["join_keys"] == []
        assert result["classification"] == "transformation"


# =============================================================================
# 11. Malformed constraint data (Req 9.6)
# =============================================================================


class TestMalformedConstraintData:
    """Constraints missing DTS:From/DTS:To raise ExtractionError."""

    def test_missing_from_attribute_raises_error(self):
        xml = f"""<DTS:Executable xmlns:DTS="{DTS_NS}">
            <DTS:PrecedenceConstraints>
                <DTS:PrecedenceConstraint
                    DTS:refId="Package.PrecedenceConstraints[C1]"
                    DTS:DTSID="{{1234}}"
                    DTS:ObjectName="C1"
                    DTS:To="Package\\TaskB" />
            </DTS:PrecedenceConstraints>
        </DTS:Executable>"""

        element = ET.fromstring(xml)
        with pytest.raises(ExtractionError) as exc_info:
            extract_precedence_constraints(element, "test.dtsx")

        assert "DTS:From" in exc_info.value.reason

    def test_missing_to_attribute_raises_error(self):
        xml = f"""<DTS:Executable xmlns:DTS="{DTS_NS}">
            <DTS:PrecedenceConstraints>
                <DTS:PrecedenceConstraint
                    DTS:refId="Package.PrecedenceConstraints[C1]"
                    DTS:DTSID="{{1234}}"
                    DTS:ObjectName="C1"
                    DTS:From="Package\\TaskA" />
            </DTS:PrecedenceConstraints>
        </DTS:Executable>"""

        element = ET.fromstring(xml)
        with pytest.raises(ExtractionError) as exc_info:
            extract_precedence_constraints(element, "test.dtsx")

        assert "DTS:To" in exc_info.value.reason

    def test_missing_both_from_and_to_raises_error(self):
        xml = f"""<DTS:Executable xmlns:DTS="{DTS_NS}">
            <DTS:PrecedenceConstraints>
                <DTS:PrecedenceConstraint
                    DTS:refId="Package.PrecedenceConstraints[C1]"
                    DTS:DTSID="{{1234}}"
                    DTS:ObjectName="C1" />
            </DTS:PrecedenceConstraints>
        </DTS:Executable>"""

        element = ET.fromstring(xml)
        with pytest.raises(ExtractionError) as exc_info:
            extract_precedence_constraints(element, "test.dtsx")

        assert "DTS:From" in exc_info.value.reason
        assert "DTS:To" in exc_info.value.reason


# =============================================================================
# 12. SQL task missing SqlTaskData (Req 8.6)
# =============================================================================


class TestSQLTaskMissingSqlTaskData:
    """Executable with no SqlTaskData returns flag indicating missing data."""

    def test_missing_object_data_returns_missing_flag(self):
        xml = f"""<DTS:Executable xmlns:DTS="{DTS_NS}"
            DTS:refId="Package\\SQLTask"
            DTS:CreationName="Microsoft.ExecuteSQLTask"
            DTS:ObjectName="Execute SQL Task">
        </DTS:Executable>"""

        element = ET.fromstring(xml)
        result = extract_sql_task(element, "test.dtsx")

        assert result["sql_data_missing"] is True
        assert result["sql_statement_source"] == ""
        assert result["connection"] == ""
        assert result["parameter_bindings"] == []

    def test_missing_sql_task_data_element_returns_missing_flag(self):
        xml = f"""<DTS:Executable xmlns:DTS="{DTS_NS}"
            xmlns:SQLTask="{SQLTASK_NS}"
            DTS:refId="Package\\SQLTask"
            DTS:CreationName="Microsoft.ExecuteSQLTask"
            DTS:ObjectName="Execute SQL Task">
            <DTS:ObjectData>
                <SomeOtherElement />
            </DTS:ObjectData>
        </DTS:Executable>"""

        element = ET.fromstring(xml)
        result = extract_sql_task(element, "test.dtsx")

        assert result["sql_data_missing"] is True
        assert result["sql_statement_source"] == ""


# =============================================================================
# 13. Failed derived column overwrite extraction (Req 10.7)
# =============================================================================


class TestDerivedColumnOverwriteFailure:
    """Derived column overwrite missing lineageId or expression fails extraction."""

    def test_overwrite_missing_lineage_id_fails_component(self):
        xml = """<component refId="Package\\Task\\DC"
            name="Derived Column"
            componentClassID="Microsoft.DerivedColumn">
            <inputs>
                <input refId="Package\\Task\\DC.Inputs[Input]"
                    name="Derived Column Input">
                    <inputColumns>
                        <inputColumn refId="Package\\Task\\DC.Inputs[Input].Columns[Col1]"
                            cachedName="Col1"
                            usageType="readWrite">
                            <properties>
                                <property name="Expression">UPPER(Col1)</property>
                                <property name="FriendlyExpression">UPPER(Col1)</property>
                            </properties>
                        </inputColumn>
                    </inputColumns>
                </input>
            </inputs>
            <outputs>
                <output refId="Package\\Task\\DC.Outputs[Output]"
                    name="Derived Column Output">
                </output>
            </outputs>
        </component>"""

        element = ET.fromstring(xml)
        result = extract_component(element)

        # Component should be marked as failed
        assert result["extraction_status"] == "failed"
        assert "lineageId" in result["failure_reason"]

    def test_overwrite_missing_expression_fails_component(self):
        xml = """<component refId="Package\\Task\\DC"
            name="Derived Column"
            componentClassID="Microsoft.DerivedColumn">
            <inputs>
                <input refId="Package\\Task\\DC.Inputs[Input]"
                    name="Derived Column Input">
                    <inputColumns>
                        <inputColumn refId="Package\\Task\\DC.Inputs[Input].Columns[Col1]"
                            cachedName="Col1"
                            lineageId="55"
                            usageType="readWrite">
                            <properties>
                                <property name="FriendlyExpression">something</property>
                            </properties>
                        </inputColumn>
                    </inputColumns>
                </input>
            </inputs>
            <outputs>
                <output refId="Package\\Task\\DC.Outputs[Output]"
                    name="Derived Column Output">
                </output>
            </outputs>
        </component>"""

        element = ET.fromstring(xml)
        result = extract_component(element)

        # Component should be marked as failed
        assert result["extraction_status"] == "failed"
        assert "Expression" in result["failure_reason"]

    def test_overwrite_missing_properties_fails_component(self):
        xml = """<component refId="Package\\Task\\DC"
            name="Derived Column"
            componentClassID="Microsoft.DerivedColumn">
            <inputs>
                <input refId="Package\\Task\\DC.Inputs[Input]"
                    name="Derived Column Input">
                    <inputColumns>
                        <inputColumn refId="Package\\Task\\DC.Inputs[Input].Columns[Col1]"
                            cachedName="Col1"
                            lineageId="55"
                            usageType="readWrite">
                        </inputColumn>
                    </inputColumns>
                </input>
            </inputs>
            <outputs>
                <output refId="Package\\Task\\DC.Outputs[Output]"
                    name="Derived Column Output">
                </output>
            </outputs>
        </component>"""

        element = ET.fromstring(xml)
        result = extract_component(element)

        # Component should be marked as failed
        assert result["extraction_status"] == "failed"
        assert (
            "properties" in result["failure_reason"].lower()
            or "required" in result["failure_reason"].lower()
        )


# =============================================================================
# 14. SqlCommandVariable with empty value (Req 8.4)
# =============================================================================


class TestSqlCommandVariableEmpty:
    """SQL task with empty SqlCommandVariable fails processing."""

    def test_empty_sql_statement_with_empty_variable_raises_error(self):
        xml = f"""<DTS:Executable xmlns:DTS="{DTS_NS}"
            xmlns:SQLTask="{SQLTASK_NS}"
            DTS:refId="Package\\SQLTask"
            DTS:CreationName="Microsoft.ExecuteSQLTask"
            DTS:ObjectName="Execute SQL Task">
            <DTS:ObjectData>
                <SQLTask:SqlTaskData
                    SQLTask:Connection="{{CONN-ID}}"
                    SQLTask:SqlStatementSource=""
                    SQLTask:SqlCommandVariable="   " />
            </DTS:ObjectData>
        </DTS:Executable>"""

        element = ET.fromstring(xml)
        with pytest.raises(ExtractionError) as exc_info:
            extract_sql_task(element, "test.dtsx")

        assert "variable reference could not be extracted" in exc_info.value.reason

    def test_absent_sql_statement_with_populated_variable_succeeds(self):
        xml = f"""<DTS:Executable xmlns:DTS="{DTS_NS}"
            xmlns:SQLTask="{SQLTASK_NS}"
            DTS:refId="Package\\SQLTask"
            DTS:CreationName="Microsoft.ExecuteSQLTask"
            DTS:ObjectName="Execute SQL Task">
            <DTS:ObjectData>
                <SQLTask:SqlTaskData
                    SQLTask:Connection="{{CONN-ID}}"
                    SQLTask:SqlCommandVariable="User::SqlQuery" />
            </DTS:ObjectData>
        </DTS:Executable>"""

        element = ET.fromstring(xml)
        result = extract_sql_task(element, "test.dtsx")

        assert result["sql_statement_source"] == "User::SqlQuery"
        assert result["sql_source_type"] == "variable"
        assert result["sql_data_missing"] is False
