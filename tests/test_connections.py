"""Unit tests for connection manager extraction from SSIS package XML."""

import xml.etree.ElementTree as ET

import pytest

from pydtsx_parser.errors import ExtractionError
from pydtsx_parser.extractors.connections import (
    extract_connection_managers,
    extract_single_connection_manager,
)

# DTS namespace URI used in test XML
DTS_NS = "www.microsoft.com/SqlServer/Dts"


def _make_package_xml(conn_managers_xml: str = "") -> ET.Element:
    """Build a minimal DTS:Executable element with optional connection managers XML."""
    xml_str = (
        f'<DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">'
        f"{conn_managers_xml}"
        f"</DTS:Executable>"
    )
    return ET.fromstring(xml_str)


def _make_single_cm(cm_xml: str) -> ET.Element:
    """Parse a single DTS:ConnectionManager element."""
    xml_str = f'<DTS:ConnectionManager xmlns:DTS="{DTS_NS}" {cm_xml}'
    return ET.fromstring(xml_str)


class TestExtractConnectionManagersContainer:
    """Tests for the top-level container extraction."""

    def test_no_connection_managers_element_returns_empty(self):
        """When no DTS:ConnectionManagers element exists, return empty list."""
        parent = _make_package_xml("")
        result = extract_connection_managers(parent)
        assert result == []

    def test_empty_connection_managers_element_returns_empty(self):
        """When DTS:ConnectionManagers exists but has no children, return empty list."""
        parent = _make_package_xml("<DTS:ConnectionManagers/>")
        result = extract_connection_managers(parent)
        assert result == []

    def test_multiple_connection_managers(self):
        """Extract multiple connection managers from same container."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[CM1]"
              DTS:CreationName="OLEDB"
              DTS:DTSID="{AAA}"
              DTS:ObjectName="CM1">
              <DTS:ObjectData>
                <DTS:ConnectionManager DTS:ConnectionString="Data Source=server1;" />
              </DTS:ObjectData>
            </DTS:ConnectionManager>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[CM2]"
              DTS:CreationName="OLEDB"
              DTS:DTSID="{BBB}"
              DTS:ObjectName="CM2">
              <DTS:ObjectData>
                <DTS:ConnectionManager DTS:ConnectionString="Data Source=server2;" />
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        assert len(result) == 2
        assert result[0]["object_name"] == "CM1"
        assert result[1]["object_name"] == "CM2"


class TestCommonAttributes:
    """Tests for common connection manager attributes."""

    def test_all_common_fields_extracted(self):
        """All common fields (refId, ObjectName, DTSID, CreationName, Description) extracted."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[MyConn]"
              DTS:CreationName="OLEDB"
              DTS:DTSID="{12345678-1234-1234-1234-123456789012}"
              DTS:ObjectName="MyConn"
              DTS:Description="My connection">
              <DTS:ObjectData>
                <DTS:ConnectionManager DTS:ConnectionString="Data Source=srv;" />
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        cm = result[0]

        assert cm["ref_id"] == "Package.ConnectionManagers[MyConn]"
        assert cm["object_name"] == "MyConn"
        assert cm["dts_id"] == "{12345678-1234-1234-1234-123456789012}"
        assert cm["creation_name"] == "OLEDB"
        assert cm["description"] == "My connection"

    def test_description_omitted_when_empty(self):
        """Description key is omitted when the attribute is empty or absent."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[NoDsc]"
              DTS:CreationName="OLEDB"
              DTS:DTSID="{AAA}"
              DTS:ObjectName="NoDsc">
              <DTS:ObjectData>
                <DTS:ConnectionManager DTS:ConnectionString="Data Source=srv;" />
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        assert "description" not in result[0]

    def test_missing_object_name_raises_extraction_error(self):
        """Missing ObjectName attribute raises ExtractionError (Req 3.7)."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[X]"
              DTS:CreationName="OLEDB"
              DTS:DTSID="{AAA}">
              <DTS:ObjectData>
                <DTS:ConnectionManager DTS:ConnectionString="Data Source=srv;" />
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        with pytest.raises(ExtractionError) as exc_info:
            extract_connection_managers(parent, file_path="test.dtsx")
        assert "ObjectName" in exc_info.value.reason

    def test_no_object_data_returns_empty_properties(self):
        """Connection manager without ObjectData returns empty properties dict."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[NoData]"
              DTS:CreationName="OLEDB"
              DTS:DTSID="{AAA}"
              DTS:ObjectName="NoData">
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        assert result[0]["properties"] == {}


class TestFlatFileExtraction:
    """Tests for FLATFILE connection manager extraction."""

    def test_flatfile_basic_properties(self):
        """Extract basic FLATFILE properties (format, locale, delimiters, etc.)."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[MyCSV]"
              DTS:CreationName="FLATFILE"
              DTS:DTSID="{111}"
              DTS:ObjectName="MyCSV"
              DTS:Description="CSV file">
              <DTS:ObjectData>
                <DTS:ConnectionManager
                  DTS:Format="Delimited"
                  DTS:LocaleID="1033"
                  DTS:HeaderRowDelimiter="_x000D__x000A_"
                  DTS:ColumnNamesInFirstDataRow="True"
                  DTS:RowDelimiter=""
                  DTS:TextQualifier="_x0022_"
                  DTS:CodePage="65001"
                  DTS:ConnectionString="C:\\data\\file.csv">
                </DTS:ConnectionManager>
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        props = result[0]["properties"]

        assert props["format"] == "Delimited"
        assert props["locale_id"] == "1033"
        assert props["header_row_delimiter"] == "_x000D__x000A_"
        assert props["column_names_in_first_data_row"] is True
        assert props["row_delimiter"] == ""
        assert props["text_qualifier"] == "_x0022_"
        assert props["code_page"] == "65001"
        assert props["connection_string"] == "C:\\data\\file.csv"

    def test_flatfile_columns_extracted(self):
        """Extract FlatFileColumns with per-column metadata."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[WithCols]"
              DTS:CreationName="FLATFILE"
              DTS:DTSID="{222}"
              DTS:ObjectName="WithCols">
              <DTS:ObjectData>
                <DTS:ConnectionManager
                  DTS:Format="Delimited"
                  DTS:LocaleID="1033"
                  DTS:HeaderRowDelimiter="_x000D__x000A_"
                  DTS:RowDelimiter=""
                  DTS:CodePage="65001"
                  DTS:ConnectionString="C:\\data\\file.csv">
                  <DTS:FlatFileColumns>
                    <DTS:FlatFileColumn
                      DTS:ColumnType="Delimited"
                      DTS:ColumnDelimiter="_x002C_"
                      DTS:MaximumWidth="50"
                      DTS:DataType="129"
                      DTS:TextQualified="True"
                      DTS:ObjectName="COLUMN_A"
                      DTS:DTSID="{COL1}" />
                    <DTS:FlatFileColumn
                      DTS:ColumnType="Delimited"
                      DTS:ColumnDelimiter="_x000D__x000A_"
                      DTS:MaximumWidth="100"
                      DTS:DataType="130"
                      DTS:TextQualified="True"
                      DTS:ObjectName="COLUMN_B"
                      DTS:DTSID="{COL2}" />
                  </DTS:FlatFileColumns>
                </DTS:ConnectionManager>
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        props = result[0]["properties"]

        assert "flat_file_columns" in props
        columns = props["flat_file_columns"]
        assert len(columns) == 2

        col1 = columns[0]
        assert col1["object_name"] == "COLUMN_A"
        assert col1["column_type"] == "Delimited"
        assert col1["column_delimiter"] == "_x002C_"
        assert col1["data_type"] == "129"
        assert col1["maximum_width"] == "50"
        assert col1["text_qualified"] is True
        assert col1["dts_id"] == "{COL1}"

        col2 = columns[1]
        assert col2["object_name"] == "COLUMN_B"
        assert col2["column_delimiter"] == "_x000D__x000A_"
        assert col2["data_type"] == "130"
        assert col2["maximum_width"] == "100"

    def test_flatfile_no_columns(self):
        """FLATFILE without FlatFileColumns has no flat_file_columns key."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[NoCols]"
              DTS:CreationName="FLATFILE"
              DTS:DTSID="{333}"
              DTS:ObjectName="NoCols">
              <DTS:ObjectData>
                <DTS:ConnectionManager
                  DTS:Format="Delimited"
                  DTS:LocaleID="1033"
                  DTS:HeaderRowDelimiter="_x000D__x000A_"
                  DTS:RowDelimiter=""
                  DTS:CodePage="1252"
                  DTS:ConnectionString="C:\\data\\file.csv">
                </DTS:ConnectionManager>
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        props = result[0]["properties"]
        assert "flat_file_columns" not in props

    def test_flatfile_column_names_in_first_row_false(self):
        """ColumnNamesInFirstDataRow False properly converted to boolean."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[NoHeader]"
              DTS:CreationName="FLATFILE"
              DTS:DTSID="{444}"
              DTS:ObjectName="NoHeader">
              <DTS:ObjectData>
                <DTS:ConnectionManager
                  DTS:Format="FixedWidth"
                  DTS:LocaleID="1033"
                  DTS:HeaderRowDelimiter="_x000D__x000A_"
                  DTS:ColumnNamesInFirstDataRow="False"
                  DTS:RowDelimiter=""
                  DTS:CodePage="1252"
                  DTS:ConnectionString="C:\\data\\file.txt">
                </DTS:ConnectionManager>
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        props = result[0]["properties"]
        assert props["format"] == "FixedWidth"
        assert props["column_names_in_first_data_row"] is False

    def test_flatfile_header_rows_to_skip(self):
        """HeaderRowsToSkip extracted as integer."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[Skip]"
              DTS:CreationName="FLATFILE"
              DTS:DTSID="{555}"
              DTS:ObjectName="Skip">
              <DTS:ObjectData>
                <DTS:ConnectionManager
                  DTS:Format="Delimited"
                  DTS:LocaleID="1033"
                  DTS:HeaderRowDelimiter="_x000D__x000A_"
                  DTS:HeaderRowsToSkip="3"
                  DTS:RowDelimiter=""
                  DTS:CodePage="65001"
                  DTS:ConnectionString="C:\\data\\file.csv">
                </DTS:ConnectionManager>
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        props = result[0]["properties"]
        assert props["header_rows_to_skip"] == 3


class TestOLEDBExtraction:
    """Tests for OLEDB connection manager extraction."""

    def test_oledb_connection_string_extracted(self):
        """OLEDB extracts the full connection string preserving all key-value pairs."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[MyDB]"
              DTS:CreationName="OLEDB"
              DTS:DTSID="{AAA}"
              DTS:ObjectName="MyDB"
              DTS:Description="Main database">
              <DTS:ObjectData>
                <DTS:ConnectionManager
                  DTS:ConnectRetryCount="1"
                  DTS:ConnectRetryInterval="5"
                  DTS:ConnectionString="Data Source=SQLSRV01;Initial Catalog=SALESDB;Provider=MSOLEDBSQL.1;Integrated Security=SSPI;Auto Translate=False;" />
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        cm = result[0]

        assert cm["creation_name"] == "OLEDB"
        assert cm["description"] == "Main database"
        props = cm["properties"]
        assert "Data Source=SQLSRV01" in props["connection_string"]
        assert "Initial Catalog=SALESDB" in props["connection_string"]
        assert "Provider=MSOLEDBSQL.1" in props["connection_string"]
        assert "Integrated Security=SSPI" in props["connection_string"]

    def test_oledb_no_connection_string(self):
        """OLEDB with no ConnectionString attribute returns empty properties."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[Empty]"
              DTS:CreationName="OLEDB"
              DTS:DTSID="{BBB}"
              DTS:ObjectName="Empty">
              <DTS:ObjectData>
                <DTS:ConnectionManager DTS:ConnectRetryCount="1" />
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        assert result[0]["properties"] == {}


class TestADONETExtraction:
    """Tests for ADO.NET:SQL connection manager extraction."""

    def test_adonet_connection_string_extracted(self):
        """ADO.NET:SQL extracts the full connection string."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[AdoConn]"
              DTS:CreationName="ADO.NET:SQL"
              DTS:DTSID="{CCC}"
              DTS:ObjectName="AdoConn"
              DTS:Description="ADO connection">
              <DTS:ObjectData>
                <DTS:ConnectionManager
                  DTS:ConnectionString="Data Source=server;Initial Catalog=DB;Integrated Security=True;Connect Timeout=30;" />
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        cm = result[0]

        assert cm["creation_name"] == "ADO.NET:SQL"
        props = cm["properties"]
        assert "Data Source=server" in props["connection_string"]
        assert "Connect Timeout=30" in props["connection_string"]


class TestOracleExtraction:
    """Tests for ORACLE connection manager extraction."""

    def test_oracle_all_properties_extracted(self):
        """Extract all Oracle-specific properties."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[DB]"
              DTS:CreationName="ORACLE"
              DTS:DTSID="{EAC9A200-C5EF-45C7-A77B-4840F05C329A}"
              DTS:ObjectName="DB"
              DTS:Description="Sales database">
              <DTS:ObjectData>
                <DTS:ConnectionManager>
                  <OraConnectionString>SERVER=oradb01:1521/orcl;USERNAME=etl_user;</OraConnectionString>
                  <OraPassword Sensitive="1">EncryptedPasswordData</OraPassword>
                  <OraRetain>False</OraRetain>
                  <OraInitialCatalog></OraInitialCatalog>
                  <OraServerName>oradb01:1521/orcl</OraServerName>
                  <OraUserName>etl_user</OraUserName>
                  <OraOracleHome>/path/to/home32</OraOracleHome>
                  <OraOracleHome64>/path/to/home64</OraOracleHome64>
                  <OraWinAuthentication>False</OraWinAuthentication>
                  <OraEnableDetailedTracing>False</OraEnableDetailedTracing>
                </DTS:ConnectionManager>
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        cm = result[0]

        assert cm["ref_id"] == "Package.ConnectionManagers[DB]"
        assert cm["object_name"] == "DB"
        assert cm["creation_name"] == "ORACLE"
        assert cm["description"] == "Sales database"

        props = cm["properties"]
        assert props["server_name"] == "oradb01:1521/orcl"
        assert props["user_name"] == "etl_user"
        assert (
            props["connection_string"] == "SERVER=oradb01:1521/orcl;USERNAME=etl_user;"
        )
        assert props["oracle_home"] == "/path/to/home32"
        assert props["oracle_home_64"] == "/path/to/home64"
        assert props["win_authentication"] is False
        assert props["retain"] is False
        assert props["initial_catalog"] == ""
        assert props["enable_detailed_tracing"] is False

    def test_oracle_sensitive_password(self):
        """Oracle password with Sensitive=1 is flagged as sensitive."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[OraConn]"
              DTS:CreationName="ORACLE"
              DTS:DTSID="{DDD}"
              DTS:ObjectName="OraConn">
              <DTS:ObjectData>
                <DTS:ConnectionManager>
                  <OraPassword Sensitive="1">SecretData</OraPassword>
                  <OraServerName>server:1521/db</OraServerName>
                  <OraUserName>user1</OraUserName>
                  <OraOracleHome></OraOracleHome>
                  <OraOracleHome64></OraOracleHome64>
                  <OraWinAuthentication>False</OraWinAuthentication>
                  <OraRetain>False</OraRetain>
                  <OraInitialCatalog></OraInitialCatalog>
                  <OraConnectionString>SERVER=server:1521/db;</OraConnectionString>
                  <OraEnableDetailedTracing>False</OraEnableDetailedTracing>
                </DTS:ConnectionManager>
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        props = result[0]["properties"]

        assert props["password"] == {"value": "SecretData", "sensitive": True}

    def test_oracle_win_authentication_true(self):
        """OraWinAuthentication True is properly converted to boolean."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[WinAuth]"
              DTS:CreationName="ORACLE"
              DTS:DTSID="{EEE}"
              DTS:ObjectName="WinAuth">
              <DTS:ObjectData>
                <DTS:ConnectionManager>
                  <OraServerName>server</OraServerName>
                  <OraUserName></OraUserName>
                  <OraOracleHome></OraOracleHome>
                  <OraOracleHome64></OraOracleHome64>
                  <OraWinAuthentication>True</OraWinAuthentication>
                  <OraRetain>True</OraRetain>
                  <OraInitialCatalog>MyCatalog</OraInitialCatalog>
                  <OraConnectionString>SERVER=server;</OraConnectionString>
                  <OraEnableDetailedTracing>True</OraEnableDetailedTracing>
                </DTS:ConnectionManager>
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        props = result[0]["properties"]

        assert props["win_authentication"] is True
        assert props["retain"] is True
        assert props["enable_detailed_tracing"] is True
        assert props["initial_catalog"] == "MyCatalog"


class TestUnknownTypeExtraction:
    """Tests for unknown connection manager type extraction."""

    def test_unknown_type_extracts_all_attributes(self):
        """Unknown types extract all ObjectData attributes generically."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[Custom]"
              DTS:CreationName="CUSTOM_TYPE"
              DTS:DTSID="{FFF}"
              DTS:ObjectName="Custom"
              DTS:Description="Custom connection">
              <DTS:ObjectData>
                <DTS:ConnectionManager
                  DTS:ConnectionString="custom=value;"
                  DTS:CustomProp="hello" />
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        cm = result[0]

        assert cm["creation_name"] == "CUSTOM_TYPE"
        props = cm["properties"]
        assert props["ConnectionString"] == "custom=value;"
        assert props["CustomProp"] == "hello"

    def test_unknown_type_extracts_child_elements(self):
        """Unknown types extract child element text values."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[WithChildren]"
              DTS:CreationName="EXOTIC"
              DTS:DTSID="{GGG}"
              DTS:ObjectName="WithChildren">
              <DTS:ObjectData>
                <DTS:ConnectionManager>
                  <ServerName>my-server</ServerName>
                  <Port>5432</Port>
                  <Database>mydb</Database>
                </DTS:ConnectionManager>
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        props = result[0]["properties"]

        assert props["ServerName"] == "my-server"
        assert props["Port"] == "5432"
        assert props["Database"] == "mydb"

    def test_unknown_type_handles_namespaced_children(self):
        """Unknown types strip namespace from child element tags."""
        xml = f"""
        <DTS:ConnectionManagers xmlns:DTS="{DTS_NS}">
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[NsChild]"
              DTS:CreationName="UNUSUAL"
              DTS:DTSID="{{HHH}}"
              DTS:ObjectName="NsChild">
              <DTS:ObjectData>
                <DTS:ConnectionManager>
                  <DTS:SomeProperty>value1</DTS:SomeProperty>
                </DTS:ConnectionManager>
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        # Need to parse with full wrapping since we have nested namespace
        parent_xml = f'<DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">{xml}</DTS:Executable>'
        parent = ET.fromstring(parent_xml)
        result = extract_connection_managers(parent)
        props = result[0]["properties"]
        assert props["SomeProperty"] == "value1"


class TestRealWorldExamples:
    """Tests against connection-manager patterns seen in real-world SSIS files."""

    def test_real_oracle_conmgr_structure(self):
        """Test extraction from DB.conmgr-style Oracle connection manager."""
        xml = f"""
        <DTS:ConnectionManagers xmlns:DTS="{DTS_NS}">
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[DB]"
              DTS:CreationName="ORACLE"
              DTS:DTSID="{{EAC9A200-C5EF-45C7-A77B-4840F05C329A}}"
              DTS:ObjectName="DB"
              DTS:Description="Sales database">
              <DTS:ObjectData>
                <DTS:ConnectionManager>
                  <OraConnectionString>SERVER=oradb01.internal.example:1521/orcl.internal.example;USERNAME=etl_user;WINAUTH=0;data source=oragw02.internal.example:1521/orcl.internal.example;user id=etl_user;</OraConnectionString>
                  <OraPassword Sensitive="1">AQAAANCMnd8BFdERjHoAwE/Cl+sBAAAA</OraPassword>
                  <OraRetain>False</OraRetain>
                  <OraInitialCatalog></OraInitialCatalog>
                  <OraServerName>oradb01.internal.example:1521/orcl.internal.example</OraServerName>
                  <OraUserName>etl_user</OraUserName>
                  <OraOracleHome></OraOracleHome>
                  <OraOracleHome64></OraOracleHome64>
                  <OraWinAuthentication>False</OraWinAuthentication>
                  <OraEnableDetailedTracing>False</OraEnableDetailedTracing>
                </DTS:ConnectionManager>
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent_xml = f'<DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">{xml}</DTS:Executable>'
        parent = ET.fromstring(parent_xml)
        result = extract_connection_managers(parent)
        cm = result[0]

        assert cm["object_name"] == "DB"
        assert cm["creation_name"] == "ORACLE"
        assert cm["description"] == "Sales database"

        props = cm["properties"]
        assert (
            props["server_name"]
            == "oradb01.internal.example:1521/orcl.internal.example"
        )
        assert props["user_name"] == "etl_user"
        assert props["password"]["sensitive"] is True
        assert props["oracle_home"] == ""
        assert props["oracle_home_64"] == ""
        assert props["win_authentication"] is False
        assert props["retain"] is False
        assert props["enable_detailed_tracing"] is False

    def test_real_oledb_connection_manager(self):
        """Test extraction from a realistic OLEDB connection manager pattern."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[DEVBOX01.SALESDB]"
              DTS:CreationName="OLEDB"
              DTS:DTSID="{6135DEE1-FF4D-44DA-852D-6D9D15558F17}"
              DTS:ObjectName="DEVBOX01.SALESDB">
              <DTS:ObjectData>
                <DTS:ConnectionManager
                  DTS:ConnectRetryCount="1"
                  DTS:ConnectRetryInterval="5"
                  DTS:ConnectionString="Data Source=SQLSRV01;Initial Catalog=SALESDB;Provider=MSOLEDBSQL.1;Integrated Security=SSPI;Auto Translate=False;Application Name=SSIS-Package-{6135DEE1-FF4D-44DA-852D-6D9D15558F17}DEVBOX01.SALESDB;" />
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        cm = result[0]

        assert cm["object_name"] == "DEVBOX01.SALESDB"
        assert cm["creation_name"] == "OLEDB"
        props = cm["properties"]
        expected_cs = "Data Source=SQLSRV01;Initial Catalog=SALESDB;Provider=MSOLEDBSQL.1;Integrated Security=SSPI;Auto Translate=False;Application Name=SSIS-Package-{6135DEE1-FF4D-44DA-852D-6D9D15558F17}DEVBOX01.SALESDB;"
        assert props["connection_string"] == expected_cs

    def test_real_adonet_connection_manager(self):
        """Test extraction from a realistic ADO.NET:SQL connection manager."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[SALESDB]"
              DTS:CreationName="ADO.NET:SQL"
              DTS:DTSID="{76B172CE-65C7-4321-9761-E2ACBCC057B9}"
              DTS:ObjectName="SALESDB">
              <DTS:ObjectData>
                <DTS:ConnectionManager
                  DTS:ConnectionString="Data Source=SQLSRV01;Initial Catalog=SALESDB;Integrated Security=True;Connect Timeout=30;Application Name=SSIS-Package-{76B172CE-65C7-4321-9761-E2ACBCC057B9}SALESDB;" />
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        cm = result[0]

        assert cm["object_name"] == "SALESDB"
        assert cm["creation_name"] == "ADO.NET:SQL"
        props = cm["properties"]
        assert "Integrated Security=True" in props["connection_string"]
        assert "Connect Timeout=30" in props["connection_string"]

    def test_real_flatfile_with_columns(self):
        """Test extraction from a realistic FLATFILE with columns."""
        xml = """
        <DTS:ConnectionManagers>
            <DTS:ConnectionManager
              DTS:refId="Package.ConnectionManagers[STATUS_LOOKUP]"
              DTS:CreationName="FLATFILE"
              DTS:Description="STATUS_LOOKUP"
              DTS:DTSID="{AFF8E09A-DF1A-473B-939A-2D697CA07387}"
              DTS:ObjectName="STATUS_LOOKUP">
              <DTS:ObjectData>
                <DTS:ConnectionManager
                  DTS:Format="Delimited"
                  DTS:LocaleID="1033"
                  DTS:HeaderRowDelimiter="_x000D__x000A_"
                  DTS:ColumnNamesInFirstDataRow="True"
                  DTS:RowDelimiter=""
                  DTS:TextQualifier="_x0022_"
                  DTS:CodePage="65001"
                  DTS:ConnectionString="C:\\data\\STATUS_LOOKUP.csv">
                  <DTS:FlatFileColumns>
                    <DTS:FlatFileColumn
                      DTS:ColumnType="Delimited"
                      DTS:ColumnDelimiter="_x002C_"
                      DTS:MaximumWidth="10"
                      DTS:DataType="129"
                      DTS:TextQualified="True"
                      DTS:ObjectName="STATUS_CODE"
                      DTS:DTSID="{63D13372-EE49-4F54-8316-1D19CA2272B6}"
                      DTS:CreationName="" />
                    <DTS:FlatFileColumn
                      DTS:ColumnType="Delimited"
                      DTS:ColumnDelimiter="_x000D__x000A_"
                      DTS:MaximumWidth="50"
                      DTS:DataType="129"
                      DTS:TextQualified="True"
                      DTS:ObjectName="STATUS_DESCR"
                      DTS:DTSID="{7D7E947E-BD96-41DD-A02B-927D21BA1471}"
                      DTS:CreationName="" />
                  </DTS:FlatFileColumns>
                </DTS:ConnectionManager>
              </DTS:ObjectData>
            </DTS:ConnectionManager>
        </DTS:ConnectionManagers>
        """
        parent = _make_package_xml(xml)
        result = extract_connection_managers(parent)
        cm = result[0]

        assert cm["object_name"] == "STATUS_LOOKUP"
        assert cm["creation_name"] == "FLATFILE"
        assert cm["description"] == "STATUS_LOOKUP"

        props = cm["properties"]
        assert props["format"] == "Delimited"
        assert props["column_names_in_first_data_row"] is True
        assert props["code_page"] == "65001"

        columns = props["flat_file_columns"]
        assert len(columns) == 2
        assert columns[0]["object_name"] == "STATUS_CODE"
        assert columns[0]["data_type"] == "129"
        assert columns[0]["maximum_width"] == "10"
        # Last column uses row delimiter
        assert columns[1]["column_delimiter"] == "_x000D__x000A_"


class TestSingleConnectionManagerExtraction:
    """Tests for extract_single_connection_manager (standalone .conmgr parsing)."""

    def test_standalone_conmgr_element(self):
        """Extract from a standalone ConnectionManager element (for .conmgr files)."""
        xml = f"""<DTS:ConnectionManager xmlns:DTS="{DTS_NS}"
          DTS:ObjectName="DB"
          DTS:DTSID="{{EAC9A200-C5EF-45C7-A77B-4840F05C329A}}"
          DTS:Description="Sales database"
          DTS:CreationName="ORACLE">
          <DTS:ObjectData>
            <DTS:ConnectionManager>
              <OraConnectionString>SERVER=srv:1521/db;</OraConnectionString>
              <OraServerName>srv:1521/db</OraServerName>
              <OraUserName>user1</OraUserName>
              <OraOracleHome></OraOracleHome>
              <OraOracleHome64></OraOracleHome64>
              <OraWinAuthentication>False</OraWinAuthentication>
              <OraRetain>False</OraRetain>
              <OraInitialCatalog></OraInitialCatalog>
              <OraEnableDetailedTracing>False</OraEnableDetailedTracing>
            </DTS:ConnectionManager>
          </DTS:ObjectData>
        </DTS:ConnectionManager>"""
        element = ET.fromstring(xml)
        result = extract_single_connection_manager(element, "DB.conmgr")

        assert result["object_name"] == "DB"
        assert result["creation_name"] == "ORACLE"
        assert result["description"] == "Sales database"
        assert result["properties"]["server_name"] == "srv:1521/db"
        assert result["properties"]["user_name"] == "user1"

    def test_standalone_missing_object_name_raises(self):
        """Standalone connection manager without ObjectName raises ExtractionError."""
        xml = f"""<DTS:ConnectionManager xmlns:DTS="{DTS_NS}"
          DTS:DTSID="{{AAA}}"
          DTS:CreationName="OLEDB">
          <DTS:ObjectData>
            <DTS:ConnectionManager DTS:ConnectionString="Data Source=srv;" />
          </DTS:ObjectData>
        </DTS:ConnectionManager>"""
        element = ET.fromstring(xml)
        with pytest.raises(ExtractionError) as exc_info:
            extract_single_connection_manager(element, "bad.conmgr")
        assert "ObjectName" in exc_info.value.reason
        assert exc_info.value.file_path == "bad.conmgr"
