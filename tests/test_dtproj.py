"""Tests for pydtsx_parser.parsers.dtproj module."""

import os

import pytest

from pydtsx_parser.errors import FileNotFoundError, MalformedXMLError
from pydtsx_parser.parsers.dtproj import parse_dtproj

# --- Fixtures ---


@pytest.fixture
def valid_dtproj(tmp_path):
    """Create a minimal valid .dtproj file with all required elements."""
    content = """\
<?xml version="1.0" encoding="utf-8"?>
<Project xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <DeploymentModel>Project</DeploymentModel>
  <ProductVersion>15.0.2000.180</ProductVersion>
  <SchemaVersion>9.0.1.0</SchemaVersion>
  <Database>
    <Name>MyProject.database</Name>
    <FullPath>MyProject.database</FullPath>
  </Database>
  <DeploymentModelSpecificContent>
    <Manifest>
      <SSIS:Project SSIS:ProtectionLevel="EncryptSensitiveWithUserKey" xmlns:SSIS="www.microsoft.com/SqlServer/SSIS">
        <SSIS:Properties>
          <SSIS:Property SSIS:Name="ID">{324075a5-9522-4353-8640-1cb689a4e598}</SSIS:Property>
          <SSIS:Property SSIS:Name="Name">MyProject</SSIS:Property>
          <SSIS:Property SSIS:Name="VersionMajor">1</SSIS:Property>
          <SSIS:Property SSIS:Name="VersionMinor">0</SSIS:Property>
          <SSIS:Property SSIS:Name="VersionBuild">0</SSIS:Property>
          <SSIS:Property SSIS:Name="VersionComments"></SSIS:Property>
          <SSIS:Property SSIS:Name="CreationDate">2021-05-25T15:15:24+10:00</SSIS:Property>
          <SSIS:Property SSIS:Name="CreatorName">DOMAIN\\user</SSIS:Property>
          <SSIS:Property SSIS:Name="CreatorComputerName">WORKSTATION</SSIS:Property>
          <SSIS:Property SSIS:Name="Description"></SSIS:Property>
          <SSIS:Property SSIS:Name="FormatVersion">1</SSIS:Property>
        </SSIS:Properties>
        <SSIS:Packages>
          <SSIS:Package SSIS:Name="Package.dtsx" SSIS:EntryPoint="1" />
          <SSIS:Package SSIS:Name="Helper.dtsx" SSIS:EntryPoint="0" />
        </SSIS:Packages>
        <SSIS:ConnectionManagers>
          <SSIS:ConnectionManager SSIS:Name="DB.conmgr" />
          <SSIS:ConnectionManager SSIS:Name="DW.conmgr" />
        </SSIS:ConnectionManagers>
        <SSIS:DeploymentInfo>
          <SSIS:ProjectConnectionParameters>
            <SSIS:Parameter SSIS:Name="CM.DB.ServerName">
              <SSIS:Properties>
                <SSIS:Property SSIS:Name="DataType">18</SSIS:Property>
                <SSIS:Property SSIS:Name="Sensitive">0</SSIS:Property>
                <SSIS:Property SSIS:Name="Required">0</SSIS:Property>
                <SSIS:Property SSIS:Name="IncludeInDebugDump">0</SSIS:Property>
                <SSIS:Property SSIS:Name="Value">server.example.com</SSIS:Property>
              </SSIS:Properties>
            </SSIS:Parameter>
            <SSIS:Parameter SSIS:Name="CM.DB.Password">
              <SSIS:Properties>
                <SSIS:Property SSIS:Name="DataType">18</SSIS:Property>
                <SSIS:Property SSIS:Name="Sensitive">1</SSIS:Property>
                <SSIS:Property SSIS:Name="Required">0</SSIS:Property>
                <SSIS:Property SSIS:Name="IncludeInDebugDump">0</SSIS:Property>
              </SSIS:Properties>
            </SSIS:Parameter>
          </SSIS:ProjectConnectionParameters>
          <SSIS:PackageInfo>
            <SSIS:PackageMetaData SSIS:Name="Package.dtsx">
              <SSIS:Properties>
                <SSIS:Property SSIS:Name="ID">{BE926AA3-3C0E-43CF-AD1C-50F5F399D555}</SSIS:Property>
                <SSIS:Property SSIS:Name="Name">Package</SSIS:Property>
                <SSIS:Property SSIS:Name="VersionMajor">1</SSIS:Property>
                <SSIS:Property SSIS:Name="VersionMinor">0</SSIS:Property>
                <SSIS:Property SSIS:Name="VersionBuild">72</SSIS:Property>
                <SSIS:Property SSIS:Name="VersionGUID">{43A796B8-24AD-4E41-958F-C821C9302BF3}</SSIS:Property>
                <SSIS:Property SSIS:Name="PackageFormatVersion">8</SSIS:Property>
                <SSIS:Property SSIS:Name="Description"></SSIS:Property>
                <SSIS:Property SSIS:Name="ProtectionLevel">1</SSIS:Property>
              </SSIS:Properties>
              <SSIS:Parameters>
                <SSIS:Parameter SSIS:Name="CM.DW.ConnectionString">
                  <SSIS:Properties>
                    <SSIS:Property SSIS:Name="DataType">18</SSIS:Property>
                    <SSIS:Property SSIS:Name="Sensitive">0</SSIS:Property>
                    <SSIS:Property SSIS:Name="Required">1</SSIS:Property>
                    <SSIS:Property SSIS:Name="IncludeInDebugDump">1</SSIS:Property>
                    <SSIS:Property SSIS:Name="Value">Data Source=localhost;</SSIS:Property>
                  </SSIS:Properties>
                </SSIS:Parameter>
              </SSIS:Parameters>
            </SSIS:PackageMetaData>
          </SSIS:PackageInfo>
        </SSIS:DeploymentInfo>
      </SSIS:Project>
    </Manifest>
  </DeploymentModelSpecificContent>
</Project>
"""
    path = tmp_path / "test.dtproj"
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def minimal_dtproj(tmp_path):
    """Create a .dtproj with only required elements."""
    content = """\
<?xml version="1.0" encoding="utf-8"?>
<Project>
  <DeploymentModel>Package</DeploymentModel>
  <ProductVersion>14.0.1000.100</ProductVersion>
  <SchemaVersion>8.0.0.0</SchemaVersion>
</Project>
"""
    path = tmp_path / "minimal.dtproj"
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def missing_deployment_model(tmp_path):
    """Create a .dtproj missing DeploymentModel."""
    content = """\
<?xml version="1.0" encoding="utf-8"?>
<Project>
  <ProductVersion>15.0.2000.180</ProductVersion>
  <SchemaVersion>9.0.1.0</SchemaVersion>
</Project>
"""
    path = tmp_path / "missing.dtproj"
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def malformed_xml_file(tmp_path):
    """Create a file with malformed XML."""
    content = "<?xml version='1.0'?>\n<Project><Unclosed>"
    path = tmp_path / "malformed.dtproj"
    path.write_text(content, encoding="utf-8")
    return str(path)


# --- Tests: Successful parsing ---


class TestParseDtprojSuccess:
    """Tests for successful .dtproj parsing."""

    def test_returns_success_flag(self, valid_dtproj):
        """Requirement 4.8: returns success indicator."""
        result = parse_dtproj(valid_dtproj)
        assert result["success"] is True

    def test_extracts_deployment_model(self, valid_dtproj):
        """Requirement 4.1: extracts deployment model."""
        result = parse_dtproj(valid_dtproj)
        assert result["deployment_model"] == "Project"

    def test_extracts_product_version(self, valid_dtproj):
        """Requirement 4.1: extracts product version."""
        result = parse_dtproj(valid_dtproj)
        assert result["product_version"] == "15.0.2000.180"

    def test_extracts_schema_version(self, valid_dtproj):
        """Requirement 4.1: extracts schema version."""
        result = parse_dtproj(valid_dtproj)
        assert result["schema_version"] == "9.0.1.0"

    def test_extracts_database_reference(self, valid_dtproj):
        """Requirement 4.1: extracts database name and full path."""
        result = parse_dtproj(valid_dtproj)
        assert result["database"]["name"] == "MyProject.database"
        assert result["database"]["full_path"] == "MyProject.database"

    def test_extracts_protection_level(self, valid_dtproj):
        """Requirement 4.2: extracts ProtectionLevel from manifest."""
        result = parse_dtproj(valid_dtproj)
        assert result["manifest"]["protection_level"] == "EncryptSensitiveWithUserKey"

    def test_extracts_project_properties(self, valid_dtproj):
        """Requirement 4.2: extracts all project properties."""
        result = parse_dtproj(valid_dtproj)
        props = result["manifest"]["project_properties"]
        assert props["id"] == "{324075a5-9522-4353-8640-1cb689a4e598}"
        assert props["name"] == "MyProject"
        assert props["version_major"] == "1"
        assert props["version_minor"] == "0"
        assert props["version_build"] == "0"
        assert props["version_comments"] == ""
        assert props["creation_date"] == "2021-05-25T15:15:24+10:00"
        assert props["creator_name"] == "DOMAIN\\user"
        assert props["creator_computer_name"] == "WORKSTATION"
        assert props["description"] == ""
        assert props["format_version"] == "1"

    def test_extracts_packages_with_entry_point(self, valid_dtproj):
        """Requirement 4.3: extracts packages with entry point flag."""
        result = parse_dtproj(valid_dtproj)
        packages = result["manifest"]["packages"]
        assert len(packages) == 2
        assert packages[0] == {"name": "Package.dtsx", "entry_point": True}
        assert packages[1] == {"name": "Helper.dtsx", "entry_point": False}

    def test_extracts_connection_manager_refs(self, valid_dtproj):
        """Requirement 4.4: extracts connection manager references."""
        result = parse_dtproj(valid_dtproj)
        cms = result["manifest"]["connection_managers"]
        assert len(cms) == 2
        assert cms[0] == {"name": "DB.conmgr"}
        assert cms[1] == {"name": "DW.conmgr"}

    def test_extracts_project_connection_parameters(self, valid_dtproj):
        """Requirement 4.5: extracts connection parameters."""
        result = parse_dtproj(valid_dtproj)
        params = result["project_connection_parameters"]
        assert len(params) == 2

        # Non-sensitive parameter has value
        server_param = params[0]
        assert server_param["name"] == "CM.DB.ServerName"
        assert server_param["data_type"] == "18"
        assert server_param["sensitive"] is False
        assert server_param["required"] is False
        assert server_param["include_in_debug_dump"] is False
        assert server_param["value"] == "server.example.com"

        # Sensitive parameter does not have value
        password_param = params[1]
        assert password_param["name"] == "CM.DB.Password"
        assert password_param["sensitive"] is True
        assert "value" not in password_param

    def test_extracts_package_info(self, valid_dtproj):
        """Requirement 4.6: extracts PackageInfo metadata and parameters."""
        result = parse_dtproj(valid_dtproj)
        pkg_info = result["package_info"]
        assert len(pkg_info) == 1

        pkg = pkg_info[0]
        assert pkg["name"] == "Package.dtsx"
        assert pkg["properties"]["id"] == "{BE926AA3-3C0E-43CF-AD1C-50F5F399D555}"
        assert pkg["properties"]["name"] == "Package"
        assert pkg["properties"]["version_build"] == "72"
        assert pkg["properties"]["package_format_version"] == "8"

        # Package-level parameters
        assert len(pkg["parameters"]) == 1
        param = pkg["parameters"][0]
        assert param["name"] == "CM.DW.ConnectionString"
        assert param["required"] is True
        assert param["include_in_debug_dump"] is True
        assert param["value"] == "Data Source=localhost;"

    def test_includes_completeness_summary(self, valid_dtproj):
        """Requirement 7.4: includes completeness summary."""
        result = parse_dtproj(valid_dtproj)
        assert "completeness_summary" in result
        summary = result["completeness_summary"]
        assert summary["total_elements"] > 0
        assert summary["total_attributes"] > 0
        assert isinstance(summary["skipped_items"], list)

    def test_minimal_dtproj_succeeds(self, minimal_dtproj):
        """Minimal file with just required elements succeeds."""
        result = parse_dtproj(minimal_dtproj)
        assert result["success"] is True
        assert result["deployment_model"] == "Package"
        assert result["product_version"] == "14.0.1000.100"
        assert result["schema_version"] == "8.0.0.0"
        assert result["database"] is None
        assert result["manifest"] is None
        assert result["project_connection_parameters"] == []
        assert result["package_info"] == []


# --- Tests: Error conditions ---


class TestParseDtprojErrors:
    """Tests for error handling in .dtproj parsing."""

    def test_missing_required_element_returns_error(self, missing_deployment_model):
        """Requirement 4.7: returns error on missing required elements."""
        result = parse_dtproj(missing_deployment_model)
        assert result["error"] is True
        assert "DeploymentModel" in result["message"]
        assert result["error_type"] == "extraction_error"
        assert result["file_path"] == missing_deployment_model

    def test_malformed_xml_raises_error(self, malformed_xml_file):
        """Requirement 4.7: raises error on malformed XML."""
        with pytest.raises(MalformedXMLError):
            parse_dtproj(malformed_xml_file)

    def test_file_not_found_raises_error(self):
        """Requirement 4.7: raises error on missing file."""
        with pytest.raises(FileNotFoundError):
            parse_dtproj("/nonexistent/path/file.dtproj")

    def test_null_path_raises_error(self):
        """Requirement 4.7: raises error on null/empty path."""
        with pytest.raises(FileNotFoundError):
            parse_dtproj("")


# --- Tests: Local example files (optional, not bundled) ---


class TestParseDtprojRealFiles:
    """Tests against local .dtproj example files, if present."""

    @pytest.fixture
    def sample_alpha_dtproj(self):
        """Path to a local example .dtproj file, if one is present."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples",
            "SampleAlpha",
            "SampleAlpha",
            "SampleAlpha.dtproj",
        )
        if not os.path.isfile(path):
            pytest.skip("Example file not available")
        return path

    def test_parses_sample_alpha_successfully(self, sample_alpha_dtproj):
        """Local example file parses without errors."""
        result = parse_dtproj(sample_alpha_dtproj)
        assert result["success"] is True
        assert result["deployment_model"] == "Project"
        assert result["product_version"] == "15.0.2000.180"
        assert result["schema_version"] == "9.0.1.0"

    def test_sample_alpha_database(self, sample_alpha_dtproj):
        """Local example file database reference is extracted."""
        result = parse_dtproj(sample_alpha_dtproj)
        assert result["database"]["name"] == "SampleAlpha.database"

    def test_sample_alpha_manifest(self, sample_alpha_dtproj):
        """Local example file manifest is extracted with correct structure."""
        result = parse_dtproj(sample_alpha_dtproj)
        manifest = result["manifest"]
        assert manifest["protection_level"] == "EncryptSensitiveWithUserKey"
        assert manifest["project_properties"]["name"] == "SampleAlpha"
        assert len(manifest["packages"]) >= 1
        assert manifest["packages"][0]["name"] == "Package.dtsx"
        assert manifest["packages"][0]["entry_point"] is True

    def test_sample_alpha_connection_managers(self, sample_alpha_dtproj):
        """Local example file connection manager references are extracted."""
        result = parse_dtproj(sample_alpha_dtproj)
        cms = result["manifest"]["connection_managers"]
        assert len(cms) >= 1
        assert cms[0]["name"] == "DB.conmgr"

    def test_sample_alpha_connection_parameters(self, sample_alpha_dtproj):
        """Local example file project connection parameters are extracted."""
        result = parse_dtproj(sample_alpha_dtproj)
        params = result["project_connection_parameters"]
        assert len(params) > 0
        # Check that sensitive password param doesn't have value
        password_params = [p for p in params if "Password" in p["name"]]
        for pp in password_params:
            assert pp["sensitive"] is True
            assert "value" not in pp
