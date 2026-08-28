"""Tests for pydtsx_parser.parsers.dtsx module."""

import os
import tempfile

import pytest

from pydtsx_parser.errors import FileNotFoundError, MalformedXMLError
from pydtsx_parser.parsers.dtsx import parse_dtsx

DTS_NS = "www.microsoft.com/SqlServer/Dts"


def _write_temp_dtsx(xml_content: str) -> str:
    """Write XML content to a temporary .dtsx file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".dtsx")
    try:
        os.write(fd, xml_content.encode("utf-8"))
    finally:
        os.close(fd)
    return path


# --- Fixtures ---


@pytest.fixture
def minimal_package_path():
    """A minimal valid .dtsx package with all common attributes."""
    xml = f'''<?xml version="1.0"?>
<DTS:Executable xmlns:DTS="{DTS_NS}"
  DTS:refId="Package"
  DTS:CreationDate="1/15/2024 10:30:00 AM"
  DTS:CreationName="Microsoft.Package"
  DTS:CreatorComputerName="DEVBOX01"
  DTS:CreatorName="EXAMPLE\\etl_user"
  DTS:DTSID="{{CD242DB1-F69E-4E09-8311-CE7A53A048C3}}"
  DTS:ExecutableType="Microsoft.Package"
  DTS:LastModifiedProductVersion="15.0.2000.180"
  DTS:LocaleID="1033"
  DTS:ObjectName="Package"
  DTS:PackageType="5"
  DTS:VersionBuild="82"
  DTS:VersionGUID="{{819869DE-84A2-4DE8-8161-7C20E389580A}}">
  <DTS:Property
    DTS:Name="PackageFormatVersion">8</DTS:Property>
</DTS:Executable>'''
    path = _write_temp_dtsx(xml)
    yield path
    os.unlink(path)


@pytest.fixture
def package_with_variables_path():
    """A .dtsx package with package-level variables."""
    xml = f'''<?xml version="1.0"?>
<DTS:Executable xmlns:DTS="{DTS_NS}"
  DTS:refId="Package"
  DTS:CreationName="Microsoft.Package"
  DTS:ObjectName="Package"
  DTS:DTSID="{{PKG-1234}}">
  <DTS:Property DTS:Name="PackageFormatVersion">8</DTS:Property>
  <DTS:Variables>
    <DTS:Variable DTS:ObjectName="MyVar" DTS:Namespace="User">
      <DTS:VariableValue DTS:DataType="8">Hello World</DTS:VariableValue>
    </DTS:Variable>
    <DTS:Variable DTS:ObjectName="Counter" DTS:Namespace="User">
      <DTS:VariableValue DTS:DataType="3">42</DTS:VariableValue>
    </DTS:Variable>
  </DTS:Variables>
</DTS:Executable>'''
    path = _write_temp_dtsx(xml)
    yield path
    os.unlink(path)


@pytest.fixture
def package_with_connections_path():
    """A .dtsx package with connection managers."""
    xml = f'''<?xml version="1.0"?>
<DTS:Executable xmlns:DTS="{DTS_NS}"
  DTS:refId="Package"
  DTS:CreationName="Microsoft.Package"
  DTS:ObjectName="Package"
  DTS:DTSID="{{PKG-CONN}}">
  <DTS:ConnectionManagers>
    <DTS:ConnectionManager
      DTS:refId="Package.ConnectionManagers[MyConn]"
      DTS:CreationName="OLEDB"
      DTS:DTSID="{{CONN-1234}}"
      DTS:ObjectName="MyConn">
      <DTS:ObjectData>
        <DTS:ConnectionManager
          DTS:ConnectionString="Data Source=server;Initial Catalog=db;" />
      </DTS:ObjectData>
    </DTS:ConnectionManager>
  </DTS:ConnectionManagers>
</DTS:Executable>'''
    path = _write_temp_dtsx(xml)
    yield path
    os.unlink(path)


@pytest.fixture
def package_with_executables_path():
    """A .dtsx package with executable tasks."""
    xml = f'''<?xml version="1.0"?>
<DTS:Executable xmlns:DTS="{DTS_NS}"
  DTS:refId="Package"
  DTS:CreationName="Microsoft.Package"
  DTS:ObjectName="Package"
  DTS:DTSID="{{PKG-EXEC}}">
  <DTS:Executables>
    <DTS:Executable
      DTS:refId="Package\\Task1"
      DTS:CreationName="Microsoft.Pipeline"
      DTS:DTSID="{{TASK-1}}"
      DTS:ObjectName="Task1"
      DTS:Description="Data Flow Task">
      <DTS:Property DTS:Name="ForceExecValue">0</DTS:Property>
      <DTS:Variables />
    </DTS:Executable>
    <DTS:Executable
      DTS:refId="Package\\Task2"
      DTS:CreationName="Microsoft.ExecuteSQLTask"
      DTS:DTSID="{{TASK-2}}"
      DTS:ObjectName="Task2">
      <DTS:Variables />
    </DTS:Executable>
  </DTS:Executables>
</DTS:Executable>'''
    path = _write_temp_dtsx(xml)
    yield path
    os.unlink(path)


@pytest.fixture
def full_package_path():
    """A complete .dtsx package with all components."""
    xml = f'''<?xml version="1.0"?>
<DTS:Executable xmlns:DTS="{DTS_NS}"
  DTS:refId="Package"
  DTS:CreationDate="1/15/2024 10:30:00 AM"
  DTS:CreationName="Microsoft.Package"
  DTS:CreatorComputerName="DEVBOX01"
  DTS:CreatorName="EXAMPLE\\etl_user"
  DTS:DTSID="{{CD242DB1-FULL-TEST-8311-CE7A53A048C3}}"
  DTS:ExecutableType="Microsoft.Package"
  DTS:LastModifiedProductVersion="15.0.2000.180"
  DTS:LocaleID="1033"
  DTS:ObjectName="Package"
  DTS:PackageType="5"
  DTS:VersionBuild="82"
  DTS:VersionGUID="{{819869DE-FULL-TEST-8161-7C20E389580A}}">
  <DTS:Property DTS:Name="PackageFormatVersion">8</DTS:Property>
  <DTS:Variables>
    <DTS:Variable DTS:ObjectName="Var1" DTS:Namespace="User">
      <DTS:VariableValue DTS:DataType="8">value1</DTS:VariableValue>
    </DTS:Variable>
  </DTS:Variables>
  <DTS:ConnectionManagers>
    <DTS:ConnectionManager
      DTS:refId="Package.ConnectionManagers[OracleConn]"
      DTS:CreationName="ORACLE"
      DTS:DTSID="{{ORA-CONN}}"
      DTS:ObjectName="OracleConn"
      DTS:Description="Oracle Connection">
      <DTS:ObjectData>
        <DTS:ConnectionManager>
          <OraServerName>server:1521/db</OraServerName>
          <OraUserName>user1</OraUserName>
        </DTS:ConnectionManager>
      </DTS:ObjectData>
    </DTS:ConnectionManager>
  </DTS:ConnectionManagers>
  <DTS:Executables>
    <DTS:Executable
      DTS:refId="Package\\LoadData"
      DTS:CreationName="Microsoft.Pipeline"
      DTS:DTSID="{{LOAD-1234}}"
      DTS:ObjectName="LoadData"
      DTS:Description="Load Data Flow">
      <DTS:Variables>
        <DTS:Variable DTS:ObjectName="TaskVar" DTS:Namespace="User">
          <DTS:VariableValue DTS:DataType="3">10</DTS:VariableValue>
        </DTS:Variable>
      </DTS:Variables>
    </DTS:Executable>
  </DTS:Executables>
</DTS:Executable>'''
    path = _write_temp_dtsx(xml)
    yield path
    os.unlink(path)


@pytest.fixture
def package_optional_attrs_path():
    """A .dtsx package with only some optional attributes present."""
    xml = f'''<?xml version="1.0"?>
<DTS:Executable xmlns:DTS="{DTS_NS}"
  DTS:refId="Package"
  DTS:CreationName="Microsoft.Package"
  DTS:ObjectName="Package"
  DTS:DTSID="{{MIN-ATTRS}}">
</DTS:Executable>'''
    path = _write_temp_dtsx(xml)
    yield path
    os.unlink(path)


# --- Tests ---


class TestParseDtsxBasicParsing:
    """Tests for basic file parsing and error handling."""

    def test_null_file_path_raises_file_not_found(self):
        """Null/empty file_path returns FileNotFoundError (Req 1.9)."""
        with pytest.raises(FileNotFoundError):
            parse_dtsx("")

    def test_none_file_path_raises_file_not_found(self):
        """None file_path returns FileNotFoundError (Req 1.9)."""
        with pytest.raises(FileNotFoundError):
            parse_dtsx(None)

    def test_nonexistent_path_raises_file_not_found(self):
        """Non-existent file path raises FileNotFoundError (Req 1.7)."""
        with pytest.raises(FileNotFoundError):
            parse_dtsx("/nonexistent/path/Package.dtsx")

    def test_malformed_xml_raises_malformed_xml_error(self):
        """Malformed XML raises MalformedXMLError (Req 1.6)."""
        path = _write_temp_dtsx("<DTS:Executable><unclosed>")
        try:
            with pytest.raises(MalformedXMLError):
                parse_dtsx(path)
        finally:
            os.unlink(path)

    def test_file_not_found_priority_over_malformed(self):
        """File not found takes priority over malformed XML (Req 1.10)."""
        with pytest.raises(FileNotFoundError):
            parse_dtsx("/nonexistent/malformed.dtsx")

    def test_successful_parse_returns_dict(self, minimal_package_path):
        """A valid .dtsx file returns a dict with expected keys."""
        result = parse_dtsx(minimal_package_path)
        assert isinstance(result, dict)
        assert "package_attributes" in result
        assert "properties" in result
        assert "variables" in result
        assert "connection_managers" in result
        assert "executables" in result
        assert "completeness_summary" in result


class TestParseDtsxPackageAttributes:
    """Tests for package attribute extraction."""

    def test_all_standard_attributes_extracted(self, minimal_package_path):
        """All standard package attributes are extracted correctly."""
        result = parse_dtsx(minimal_package_path)
        attrs = result["package_attributes"]

        assert attrs["ref_id"] == "Package"
        assert attrs["creation_date"] == "1/15/2024 10:30:00 AM"
        assert attrs["creation_name"] == "Microsoft.Package"
        assert attrs["creator_computer_name"] == "DEVBOX01"
        assert attrs["creator_name"] == "EXAMPLE\\etl_user"
        assert attrs["dts_id"] == "{CD242DB1-F69E-4E09-8311-CE7A53A048C3}"
        assert attrs["executable_type"] == "Microsoft.Package"
        assert attrs["last_modified_product_version"] == "15.0.2000.180"
        assert attrs["locale_id"] == "1033"
        assert attrs["object_name"] == "Package"
        assert attrs["package_type"] == "5"
        assert attrs["version_build"] == "82"
        assert attrs["version_guid"] == "{819869DE-84A2-4DE8-8161-7C20E389580A}"

    def test_optional_attributes_omitted_when_absent(self, package_optional_attrs_path):
        """Optional attributes NOT present in XML are omitted (Req 1.8)."""
        result = parse_dtsx(package_optional_attrs_path)
        attrs = result["package_attributes"]

        # These were not in the XML, should be absent (not null/empty)
        assert "creation_date" not in attrs
        assert "creator_computer_name" not in attrs
        assert "creator_name" not in attrs
        assert "executable_type" not in attrs
        assert "last_modified_product_version" not in attrs
        assert "locale_id" not in attrs
        assert "package_type" not in attrs
        assert "version_build" not in attrs
        assert "version_guid" not in attrs

        # These WERE in the XML and should be present
        assert attrs["ref_id"] == "Package"
        assert attrs["creation_name"] == "Microsoft.Package"
        assert attrs["object_name"] == "Package"
        assert attrs["dts_id"] == "{MIN-ATTRS}"

    def test_raw_attributes_included(self, minimal_package_path):
        """raw_attributes sub-object contains ALL attributes from root element."""
        result = parse_dtsx(minimal_package_path)
        raw = result["package_attributes"]["raw_attributes"]

        assert isinstance(raw, dict)
        # Should contain DTS-prefixed attribute names
        assert "DTS:refId" in raw
        assert "DTS:ObjectName" in raw
        assert "DTS:CreationName" in raw
        assert raw["DTS:refId"] == "Package"

    def test_no_null_values_in_attributes(self, package_optional_attrs_path):
        """No attribute value should be None in the output (Req 1.8)."""
        result = parse_dtsx(package_optional_attrs_path)
        attrs = result["package_attributes"]

        for key, value in attrs.items():
            if key == "raw_attributes":
                continue
            assert value is not None, f"Attribute '{key}' should not be None"


class TestParseDtsxProperties:
    """Tests for DTS:Property child element extraction."""

    def test_properties_extracted(self, minimal_package_path):
        """DTS:Property children are extracted as name/value pairs."""
        result = parse_dtsx(minimal_package_path)
        properties = result["properties"]

        assert len(properties) == 1
        assert properties[0]["name"] == "PackageFormatVersion"
        assert properties[0]["value"] == "8"

    def test_properties_empty_when_none(self, package_optional_attrs_path):
        """Properties list is empty when no DTS:Property children exist."""
        result = parse_dtsx(package_optional_attrs_path)
        assert result["properties"] == []

    def test_multiple_properties(self):
        """Multiple DTS:Property children are all extracted."""
        xml = f'''<?xml version="1.0"?>
<DTS:Executable xmlns:DTS="{DTS_NS}"
  DTS:refId="Package"
  DTS:CreationName="Microsoft.Package"
  DTS:ObjectName="Package"
  DTS:DTSID="{{MULTI-PROP}}">
  <DTS:Property DTS:Name="PackageFormatVersion">8</DTS:Property>
  <DTS:Property DTS:Name="ProtectionLevel">0</DTS:Property>
  <DTS:Property DTS:Name="VersionComments">Test package</DTS:Property>
</DTS:Executable>'''
        path = _write_temp_dtsx(xml)
        try:
            result = parse_dtsx(path)
            assert len(result["properties"]) == 3
            assert result["properties"][0] == {
                "name": "PackageFormatVersion",
                "value": "8",
            }
            assert result["properties"][1] == {"name": "ProtectionLevel", "value": "0"}
            assert result["properties"][2] == {
                "name": "VersionComments",
                "value": "Test package",
            }
        finally:
            os.unlink(path)


class TestParseDtsxVariables:
    """Tests for variable extraction."""

    def test_variables_extracted(self, package_with_variables_path):
        """Package-level variables are extracted."""
        result = parse_dtsx(package_with_variables_path)
        variables = result["variables"]

        assert len(variables) == 2
        assert variables[0]["name"] == "MyVar"
        assert variables[0]["namespace"] == "User"
        assert variables[0]["data_type"] == "8"
        assert variables[0]["value"] == "Hello World"
        assert variables[0]["scope"] == "Package"
        assert variables[1]["name"] == "Counter"
        assert variables[1]["value"] == "42"

    def test_variables_empty_when_none(self, minimal_package_path):
        """Variables list is empty when no DTS:Variables element exists."""
        result = parse_dtsx(minimal_package_path)
        assert result["variables"] == []


class TestParseDtsxConnectionManagers:
    """Tests for connection manager extraction."""

    def test_connection_managers_extracted(self, package_with_connections_path):
        """Connection managers are extracted with properties."""
        result = parse_dtsx(package_with_connections_path)
        conns = result["connection_managers"]

        assert len(conns) == 1
        assert conns[0]["object_name"] == "MyConn"
        assert conns[0]["creation_name"] == "OLEDB"
        assert conns[0]["dts_id"] == "{CONN-1234}"
        assert "connection_string" in conns[0]["properties"]

    def test_connection_managers_empty_when_none(self, minimal_package_path):
        """Connection managers list is empty when none exist."""
        result = parse_dtsx(minimal_package_path)
        assert result["connection_managers"] == []


class TestParseDtsxExecutables:
    """Tests for executable extraction."""

    def test_executables_extracted(self, package_with_executables_path):
        """Executables are extracted with their attributes."""
        result = parse_dtsx(package_with_executables_path)
        execs = result["executables"]

        assert len(execs) == 2
        assert execs[0]["object_name"] == "Task1"
        assert execs[0]["creation_name"] == "Microsoft.Pipeline"
        assert execs[0]["description"] == "Data Flow Task"
        assert execs[1]["object_name"] == "Task2"
        assert execs[1]["creation_name"] == "Microsoft.ExecuteSQLTask"

    def test_executables_empty_when_none(self, minimal_package_path):
        """Executables list is empty when no DTS:Executables element exists."""
        result = parse_dtsx(minimal_package_path)
        assert result["executables"] == []


class TestParseDtsxCompletenessSummary:
    """Tests for completeness summary."""

    def test_completeness_summary_has_required_keys(self, minimal_package_path):
        """Completeness summary contains total_elements, total_attributes, skipped_items."""
        result = parse_dtsx(minimal_package_path)
        summary = result["completeness_summary"]

        assert "total_elements" in summary
        assert "total_attributes" in summary
        assert "skipped_items" in summary

    def test_completeness_counts_are_positive(self, minimal_package_path):
        """Element and attribute counts are positive for a valid package."""
        result = parse_dtsx(minimal_package_path)
        summary = result["completeness_summary"]

        assert summary["total_elements"] > 0
        assert summary["total_attributes"] > 0

    def test_completeness_skipped_items_is_list(self, minimal_package_path):
        """skipped_items is a list (possibly empty)."""
        result = parse_dtsx(minimal_package_path)
        assert isinstance(result["completeness_summary"]["skipped_items"], list)


class TestParseDtsxFullIntegration:
    """Integration tests for full package parsing."""

    def test_full_package_all_sections(self, full_package_path):
        """A full package has all sections populated correctly."""
        result = parse_dtsx(full_package_path)

        # Package attributes
        attrs = result["package_attributes"]
        assert attrs["object_name"] == "Package"
        assert attrs["creation_date"] == "1/15/2024 10:30:00 AM"
        assert "raw_attributes" in attrs

        # Properties
        assert len(result["properties"]) == 1
        assert result["properties"][0]["name"] == "PackageFormatVersion"

        # Variables
        assert len(result["variables"]) == 1
        assert result["variables"][0]["name"] == "Var1"
        assert result["variables"][0]["scope"] == "Package"

        # Connection managers
        assert len(result["connection_managers"]) == 1
        assert result["connection_managers"][0]["object_name"] == "OracleConn"
        assert result["connection_managers"][0]["creation_name"] == "ORACLE"

        # Executables
        assert len(result["executables"]) == 1
        assert result["executables"][0]["object_name"] == "LoadData"

        # Completeness summary
        assert result["completeness_summary"]["total_elements"] > 0

    def test_xml_comment_counted_as_skipped(self):
        """XML comments are included in skipped_items."""
        xml = f'''<?xml version="1.0"?>
<DTS:Executable xmlns:DTS="{DTS_NS}"
  DTS:refId="Package"
  DTS:CreationName="Microsoft.Package"
  DTS:ObjectName="Package"
  DTS:DTSID="{{COMMENT-PKG}}">
  <!-- This is a comment -->
  <DTS:Property DTS:Name="PackageFormatVersion">8</DTS:Property>
</DTS:Executable>'''
        path = _write_temp_dtsx(xml)
        try:
            result = parse_dtsx(path)
            skipped = result["completeness_summary"]["skipped_items"]
            assert len(skipped) >= 1
            assert any("comment" in item.lower() or "<!--" in item for item in skipped)
        finally:
            os.unlink(path)
