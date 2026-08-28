"""Tests for pydtsx_parser.parsers.conmgr module."""

import os
import tempfile

import pytest

from pydtsx_parser.errors import ExtractionError, FileNotFoundError, MalformedXMLError
from pydtsx_parser.parsers.conmgr import parse_conmgr

DTS_NS = "www.microsoft.com/SqlServer/Dts"


def _write_temp_conmgr(xml_content: str) -> str:
    """Write XML content to a temporary .conmgr file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".conmgr")
    try:
        os.write(fd, xml_content.encode("utf-8"))
    finally:
        os.close(fd)
    return path


# --- Fixtures ---


@pytest.fixture
def oracle_conmgr_path():
    """A standalone ORACLE .conmgr file."""
    xml = f'''<?xml version="1.0"?>
<DTS:ConnectionManager xmlns:DTS="{DTS_NS}"
  DTS:ObjectName="DB"
  DTS:DTSID="{{EAC9A200-C5EF-45C7-A77B-4840F05C329A}}"
  DTS:Description="Sales database"
  DTS:CreationName="ORACLE">
  <DTS:ObjectData>
    <DTS:ConnectionManager>
      <OraConnectionString>SERVER=myserver:1521/mydb;USERNAME=user1;</OraConnectionString>
      <OraPassword Sensitive="1">encrypted_pwd</OraPassword>
      <OraRetain>False</OraRetain>
      <OraInitialCatalog></OraInitialCatalog>
      <OraServerName>myserver:1521/mydb</OraServerName>
      <OraUserName>user1</OraUserName>
      <OraOracleHome></OraOracleHome>
      <OraOracleHome64></OraOracleHome64>
      <OraWinAuthentication>False</OraWinAuthentication>
      <OraEnableDetailedTracing>False</OraEnableDetailedTracing>
    </DTS:ConnectionManager>
  </DTS:ObjectData>
</DTS:ConnectionManager>'''
    path = _write_temp_conmgr(xml)
    yield path
    os.unlink(path)


@pytest.fixture
def oledb_conmgr_path():
    """A standalone OLEDB .conmgr file."""
    xml = f'''<?xml version="1.0"?>
<DTS:ConnectionManager xmlns:DTS="{DTS_NS}"
  DTS:ObjectName="MyDB"
  DTS:DTSID="{{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}}"
  DTS:CreationName="OLEDB">
  <DTS:ObjectData>
    <DTS:ConnectionManager
      DTS:ConnectionString="Data Source=SERVER1;Initial Catalog=MyDB;Provider=MSOLEDBSQL.1;Integrated Security=SSPI;" />
  </DTS:ObjectData>
</DTS:ConnectionManager>'''
    path = _write_temp_conmgr(xml)
    yield path
    os.unlink(path)


@pytest.fixture
def flatfile_conmgr_path():
    """A standalone FLATFILE .conmgr file."""
    xml = f'''<?xml version="1.0"?>
<DTS:ConnectionManager xmlns:DTS="{DTS_NS}"
  DTS:ObjectName="MyCSV"
  DTS:DTSID="{{B2C3D4E5-F6A7-8901-BCDE-F12345678901}}"
  DTS:CreationName="FLATFILE">
  <DTS:ObjectData>
    <DTS:ConnectionManager
      DTS:Format="Delimited"
      DTS:LocaleID="1033"
      DTS:HeaderRowDelimiter="_x000D__x000A_"
      DTS:ColumnNamesInFirstDataRow="True"
      DTS:RowDelimiter=""
      DTS:TextQualifier="_x0022_"
      DTS:CodePage="1252"
      DTS:ConnectionString="C:\\data\\input.csv">
      <DTS:FlatFileColumns>
        <DTS:FlatFileColumn
          DTS:ObjectName="Col1"
          DTS:ColumnType="Delimited"
          DTS:ColumnDelimiter="_x002C_"
          DTS:DataType="130"
          DTS:MaximumWidth="50"
          DTS:TextQualified="True"
          DTS:DTSID="{{C3D4E5F6-A7B8-9012-CDEF-123456789012}}" />
      </DTS:FlatFileColumns>
    </DTS:ConnectionManager>
  </DTS:ObjectData>
</DTS:ConnectionManager>'''
    path = _write_temp_conmgr(xml)
    yield path
    os.unlink(path)


# --- Tests: Successful Parsing ---


class TestParseConmgrOracle:
    """Tests for parsing ORACLE .conmgr files."""

    def test_extracts_object_name(self, oracle_conmgr_path):
        result = parse_conmgr(oracle_conmgr_path)
        assert result["connection_manager"]["object_name"] == "DB"

    def test_extracts_dts_id(self, oracle_conmgr_path):
        result = parse_conmgr(oracle_conmgr_path)
        assert (
            result["connection_manager"]["dts_id"]
            == "{EAC9A200-C5EF-45C7-A77B-4840F05C329A}"
        )

    def test_extracts_creation_name(self, oracle_conmgr_path):
        result = parse_conmgr(oracle_conmgr_path)
        assert result["connection_manager"]["creation_name"] == "ORACLE"

    def test_extracts_description(self, oracle_conmgr_path):
        result = parse_conmgr(oracle_conmgr_path)
        assert result["connection_manager"]["description"] == "Sales database"

    def test_extracts_oracle_properties(self, oracle_conmgr_path):
        result = parse_conmgr(oracle_conmgr_path)
        props = result["connection_manager"]["properties"]
        assert props["server_name"] == "myserver:1521/mydb"
        assert props["user_name"] == "user1"
        assert props["win_authentication"] is False
        assert props["retain"] is False
        assert props["enable_detailed_tracing"] is False

    def test_oracle_sensitive_password(self, oracle_conmgr_path):
        result = parse_conmgr(oracle_conmgr_path)
        props = result["connection_manager"]["properties"]
        assert props["password"]["sensitive"] is True
        assert props["password"]["value"] == "encrypted_pwd"

    def test_completeness_summary_present(self, oracle_conmgr_path):
        result = parse_conmgr(oracle_conmgr_path)
        summary = result["completeness_summary"]
        assert "total_elements" in summary
        assert "total_attributes" in summary
        assert "skipped_items" in summary
        assert summary["total_elements"] > 0
        assert summary["total_attributes"] > 0


class TestParseConmgrOledb:
    """Tests for parsing OLEDB .conmgr files."""

    def test_extracts_object_name(self, oledb_conmgr_path):
        result = parse_conmgr(oledb_conmgr_path)
        assert result["connection_manager"]["object_name"] == "MyDB"

    def test_extracts_creation_name(self, oledb_conmgr_path):
        result = parse_conmgr(oledb_conmgr_path)
        assert result["connection_manager"]["creation_name"] == "OLEDB"

    def test_extracts_connection_string(self, oledb_conmgr_path):
        result = parse_conmgr(oledb_conmgr_path)
        props = result["connection_manager"]["properties"]
        assert "Data Source=SERVER1" in props["connection_string"]
        assert "Initial Catalog=MyDB" in props["connection_string"]
        assert "Provider=MSOLEDBSQL.1" in props["connection_string"]


class TestParseConmgrFlatfile:
    """Tests for parsing FLATFILE .conmgr files."""

    def test_extracts_object_name(self, flatfile_conmgr_path):
        result = parse_conmgr(flatfile_conmgr_path)
        assert result["connection_manager"]["object_name"] == "MyCSV"

    def test_extracts_creation_name(self, flatfile_conmgr_path):
        result = parse_conmgr(flatfile_conmgr_path)
        assert result["connection_manager"]["creation_name"] == "FLATFILE"

    def test_extracts_flat_file_columns(self, flatfile_conmgr_path):
        result = parse_conmgr(flatfile_conmgr_path)
        props = result["connection_manager"]["properties"]
        assert "flat_file_columns" in props
        assert len(props["flat_file_columns"]) == 1
        col = props["flat_file_columns"][0]
        assert col["object_name"] == "Col1"
        assert col["column_type"] == "Delimited"
        assert col["data_type"] == "130"

    def test_extracts_format_properties(self, flatfile_conmgr_path):
        result = parse_conmgr(flatfile_conmgr_path)
        props = result["connection_manager"]["properties"]
        assert props["format"] == "Delimited"
        assert props["column_names_in_first_data_row"] is True
        assert props["code_page"] == "1252"


# --- Tests: Error Handling ---


class TestParseConmgrErrors:
    """Tests for error handling in conmgr parsing."""

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_conmgr("nonexistent_file.conmgr")

    def test_empty_path(self):
        with pytest.raises(FileNotFoundError):
            parse_conmgr("")

    def test_malformed_xml(self):
        path = _write_temp_conmgr("<invalid xml &&&")
        try:
            with pytest.raises(MalformedXMLError):
                parse_conmgr(path)
        finally:
            os.unlink(path)

    def test_missing_object_name(self):
        xml = f'''<?xml version="1.0"?>
<DTS:ConnectionManager xmlns:DTS="{DTS_NS}"
  DTS:DTSID="{{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}}"
  DTS:CreationName="OLEDB">
  <DTS:ObjectData>
    <DTS:ConnectionManager
      DTS:ConnectionString="Data Source=SERVER1;" />
  </DTS:ObjectData>
</DTS:ConnectionManager>'''
        path = _write_temp_conmgr(xml)
        try:
            with pytest.raises(ExtractionError):
                parse_conmgr(path)
        finally:
            os.unlink(path)


# --- Tests: Equivalence with inline connection managers ---


class TestConmgrInlineEquivalence:
    """Tests verifying standalone .conmgr output matches inline extraction."""

    def test_oracle_structure_matches_inline(self, oracle_conmgr_path):
        """Standalone .conmgr output has same keys as inline extraction."""
        result = parse_conmgr(oracle_conmgr_path)
        cm = result["connection_manager"]
        # Same keys as what extract_single_connection_manager produces
        assert "ref_id" in cm
        assert "object_name" in cm
        assert "dts_id" in cm
        assert "creation_name" in cm
        assert "properties" in cm

    def test_oledb_structure_matches_inline(self, oledb_conmgr_path):
        """OLEDB standalone .conmgr has same structure as inline."""
        result = parse_conmgr(oledb_conmgr_path)
        cm = result["connection_manager"]
        assert "ref_id" in cm
        assert "object_name" in cm
        assert "dts_id" in cm
        assert "creation_name" in cm
        assert "properties" in cm
        assert "connection_string" in cm["properties"]
