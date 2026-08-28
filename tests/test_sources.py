"""Unit tests for source component extraction."""

import xml.etree.ElementTree as ET

from pydtsx_parser.extractors.components import extract_component
from pydtsx_parser.extractors.sources import (
    extract_source_config,
    is_source_component,
)


class TestIsSourceComponent:
    """Tests for is_source_component classification."""

    def test_oledb_source(self):
        assert is_source_component("Microsoft.OLEDBSource") is True

    def test_flat_file_source(self):
        assert is_source_component("Microsoft.FlatFileSource") is True

    def test_oracle_source(self):
        assert is_source_component("Microsoft.SSISOracleSrc") is True

    def test_destination_not_source(self):
        assert is_source_component("Microsoft.OLEDBDestination") is False

    def test_transformation_not_source(self):
        assert is_source_component("Microsoft.Sort") is False

    def test_unknown_not_source(self):
        assert is_source_component("SomeUnknown.Component") is False

    def test_empty_string_not_source(self):
        assert is_source_component("") is False


class TestExtractSourceConfig:
    """Tests for extract_source_config function."""

    def test_oledb_source_with_sql_command(self):
        """OLEDBSource with AccessMode=2 (SQL Command) extracts SqlCommand."""
        xml_str = (
            '<component refId="Package\\DFT\\Src" name="OLE DB Source"'
            ' componentClassID="Microsoft.OLEDBSource">'
            "  <properties>"
            '    <property name="AccessMode">2</property>'
            '    <property name="SqlCommand">SELECT * FROM PROJECTS</property>'
            '    <property name="OpenRowset"></property>'
            '    <property name="SqlCommandVariable"></property>'
            '    <property name="OpenRowsetVariable"></property>'
            "  </properties>"
            "  <connections>"
            '    <connection refId="Package\\DFT\\Src.Connections[OleDbConnection]"'
            '        connectionManagerID="Package.ConnectionManagers[DB]" />'
            "  </connections>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        config = extract_source_config(elem)

        assert config["access_mode"] == "2"
        assert config["sql_command"] == "SELECT * FROM PROJECTS"
        assert config["open_rowset"] == ""
        assert config["sql_command_variable"] == ""
        assert config["open_rowset_variable"] == ""
        assert config["connection_manager_ref"] == "Package.ConnectionManagers[DB]"

    def test_oledb_source_with_open_rowset(self):
        """OLEDBSource with AccessMode=0 (table/view) extracts OpenRowset."""
        xml_str = (
            '<component refId="Package\\DFT\\Src" name="OLE DB Source"'
            ' componentClassID="Microsoft.OLEDBSource">'
            "  <properties>"
            '    <property name="AccessMode">0</property>'
            '    <property name="SqlCommand"></property>'
            '    <property name="OpenRowset">[dbo].[Projects]</property>'
            '    <property name="SqlCommandVariable"></property>'
            '    <property name="OpenRowsetVariable"></property>'
            "  </properties>"
            "  <connections>"
            '    <connection refId="Package\\DFT\\Src.Connections[OleDbConnection]"'
            '        connectionManagerID="Package.ConnectionManagers[LocalDB]" />'
            "  </connections>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        config = extract_source_config(elem)

        assert config["access_mode"] == "0"
        assert config["sql_command"] == ""
        assert config["open_rowset"] == "[dbo].[Projects]"
        assert config["connection_manager_ref"] == "Package.ConnectionManagers[LocalDB]"

    def test_oledb_source_with_sql_command_variable(self):
        """OLEDBSource with AccessMode=3 (SQL from variable) extracts SqlCommandVariable."""
        xml_str = (
            '<component refId="Package\\DFT\\Src" name="OLE DB Source"'
            ' componentClassID="Microsoft.OLEDBSource">'
            "  <properties>"
            '    <property name="AccessMode">3</property>'
            '    <property name="SqlCommand"></property>'
            '    <property name="OpenRowset"></property>'
            '    <property name="SqlCommandVariable">User::SqlQuery</property>'
            '    <property name="OpenRowsetVariable"></property>'
            "  </properties>"
            "  <connections>"
            '    <connection refId="conn1"'
            '        connectionManagerID="Package.ConnectionManagers[DB1]" />'
            "  </connections>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        config = extract_source_config(elem)

        assert config["access_mode"] == "3"
        assert config["sql_command"] == ""
        assert config["sql_command_variable"] == "User::SqlQuery"
        assert config["connection_manager_ref"] == "Package.ConnectionManagers[DB1]"

    def test_oledb_source_with_open_rowset_variable(self):
        """OLEDBSource with AccessMode=1 (table from variable) extracts OpenRowsetVariable."""
        xml_str = (
            '<component refId="Package\\DFT\\Src" name="OLE DB Source"'
            ' componentClassID="Microsoft.OLEDBSource">'
            "  <properties>"
            '    <property name="AccessMode">1</property>'
            '    <property name="SqlCommand"></property>'
            '    <property name="OpenRowset"></property>'
            '    <property name="SqlCommandVariable"></property>'
            '    <property name="OpenRowsetVariable">User::TableName</property>'
            "  </properties>"
            "  <connections>"
            '    <connection refId="conn1"'
            '        connectionManagerID="Package.ConnectionManagers[DB2]" />'
            "  </connections>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        config = extract_source_config(elem)

        assert config["access_mode"] == "1"
        assert config["open_rowset_variable"] == "User::TableName"
        assert config["connection_manager_ref"] == "Package.ConnectionManagers[DB2]"

    def test_flat_file_source(self):
        """FlatFileSource extracts AccessMode and connection reference."""
        xml_str = (
            '<component refId="Package\\DFT\\FF" name="Flat File Source"'
            ' componentClassID="Microsoft.FlatFileSource">'
            "  <properties>"
            '    <property name="AccessMode">0</property>'
            "  </properties>"
            "  <connections>"
            '    <connection refId="conn1"'
            '        connectionManagerID="Package.ConnectionManagers[FlatFile1]" />'
            "  </connections>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        config = extract_source_config(elem)

        assert config["access_mode"] == "0"
        assert config["sql_command"] == ""
        assert config["open_rowset"] == ""
        assert config["sql_command_variable"] == ""
        assert config["open_rowset_variable"] == ""
        assert (
            config["connection_manager_ref"] == "Package.ConnectionManagers[FlatFile1]"
        )

    def test_no_properties_returns_empty_defaults(self):
        """Source with no properties container returns all empty defaults."""
        xml_str = (
            '<component refId="Package\\DFT\\Src" name="Source"'
            ' componentClassID="Microsoft.OLEDBSource">'
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        config = extract_source_config(elem)

        assert config["access_mode"] == ""
        assert config["sql_command"] == ""
        assert config["open_rowset"] == ""
        assert config["sql_command_variable"] == ""
        assert config["open_rowset_variable"] == ""
        assert config["connection_manager_ref"] == ""

    def test_no_connections_returns_empty_ref(self):
        """Source with no connections element returns empty connection ref."""
        xml_str = (
            '<component refId="Package\\DFT\\Src" name="Source"'
            ' componentClassID="Microsoft.OLEDBSource">'
            "  <properties>"
            '    <property name="AccessMode">2</property>'
            '    <property name="SqlCommand">SELECT 1</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        config = extract_source_config(elem)

        assert config["access_mode"] == "2"
        assert config["sql_command"] == "SELECT 1"
        assert config["connection_manager_ref"] == ""

    def test_oracle_source(self):
        """SSISOracleSrc extracts source config same as OLEDBSource."""
        xml_str = (
            '<component refId="Package\\DFT\\OraSource" name="Oracle Source"'
            ' componentClassID="Microsoft.SSISOracleSrc">'
            "  <properties>"
            '    <property name="AccessMode">0</property>'
            '    <property name="SqlCommand">SELECT * FROM DUAL</property>'
            '    <property name="OpenRowset">PROJECTS</property>'
            "  </properties>"
            "  <connections>"
            '    <connection refId="conn1"'
            '        connectionManagerID="Package.ConnectionManagers[OracleRM]" />'
            "  </connections>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        config = extract_source_config(elem)

        assert config["access_mode"] == "0"
        assert config["sql_command"] == "SELECT * FROM DUAL"
        assert config["open_rowset"] == "PROJECTS"
        assert (
            config["connection_manager_ref"] == "Package.ConnectionManagers[OracleRM]"
        )


class TestExtractComponentSourceIntegration:
    """Tests for source config integration in extract_component."""

    def test_oledb_source_has_source_config(self):
        """extract_component adds source_config for OLEDBSource."""
        xml_str = (
            '<component refId="Package\\DFT\\Src" name="OLE DB Source"'
            ' componentClassID="Microsoft.OLEDBSource">'
            "  <properties>"
            '    <property name="AccessMode">2</property>'
            '    <property name="SqlCommand">SELECT * FROM PROJECTS</property>'
            '    <property name="OpenRowset"></property>'
            '    <property name="SqlCommandVariable"></property>'
            '    <property name="OpenRowsetVariable"></property>'
            "  </properties>"
            "  <connections>"
            '    <connection refId="conn1"'
            '        connectionManagerID="Package.ConnectionManagers[DB]" />'
            "  </connections>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["classification"] == "source"
        assert "source_config" in result
        assert result["source_config"]["access_mode"] == "2"
        assert result["source_config"]["sql_command"] == "SELECT * FROM PROJECTS"
        assert (
            result["source_config"]["connection_manager_ref"]
            == "Package.ConnectionManagers[DB]"
        )

    def test_flat_file_source_has_source_config(self):
        """extract_component adds source_config for FlatFileSource."""
        xml_str = (
            '<component refId="Package\\DFT\\FF" name="Flat File Source"'
            ' componentClassID="Microsoft.FlatFileSource">'
            "  <properties>"
            '    <property name="AccessMode">0</property>'
            "  </properties>"
            "  <connections>"
            '    <connection refId="conn1"'
            '        connectionManagerID="Package.ConnectionManagers[FlatFile1]" />'
            "  </connections>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["classification"] == "source"
        assert "source_config" in result
        assert result["source_config"]["access_mode"] == "0"
        assert (
            result["source_config"]["connection_manager_ref"]
            == "Package.ConnectionManagers[FlatFile1]"
        )

    def test_oracle_source_has_source_config(self):
        """extract_component adds source_config for SSISOracleSrc."""
        xml_str = (
            '<component refId="Package\\DFT\\OraSource" name="Oracle Source"'
            ' componentClassID="Microsoft.SSISOracleSrc">'
            "  <properties>"
            '    <property name="AccessMode">0</property>'
            '    <property name="SqlCommand">SELECT * FROM DUAL</property>'
            "  </properties>"
            "  <connections>"
            '    <connection refId="conn1"'
            '        connectionManagerID="Package.ConnectionManagers[OracleRM]" />'
            "  </connections>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["classification"] == "source"
        assert "source_config" in result
        assert result["source_config"]["access_mode"] == "0"
        assert result["source_config"]["sql_command"] == "SELECT * FROM DUAL"

    def test_destination_has_no_source_config(self):
        """extract_component does NOT add source_config for destinations."""
        xml_str = (
            '<component refId="Package\\DFT\\Dest" name="OLE DB Dest"'
            ' componentClassID="Microsoft.OLEDBDestination">'
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["classification"] == "destination"
        assert "source_config" not in result

    def test_transformation_has_no_source_config(self):
        """extract_component does NOT add source_config for transformations."""
        xml_str = (
            '<component refId="Package\\DFT\\DC" name="Derived Column"'
            ' componentClassID="Microsoft.DerivedColumn">'
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["classification"] == "transformation"
        assert "source_config" not in result

    def test_source_with_no_properties_still_has_source_config(self):
        """Source with no configured properties still includes source_config with empty values."""
        xml_str = (
            '<component refId="Package\\DFT\\Src" name="Empty Source"'
            ' componentClassID="Microsoft.OLEDBSource">'
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert "source_config" in result
        assert result["source_config"]["access_mode"] == ""
        assert result["source_config"]["sql_command"] == ""
        assert result["source_config"]["open_rowset"] == ""
        assert result["source_config"]["sql_command_variable"] == ""
        assert result["source_config"]["open_rowset_variable"] == ""
        assert result["source_config"]["connection_manager_ref"] == ""
