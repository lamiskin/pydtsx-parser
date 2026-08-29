"""Smoke tests for the optional MCP server.

The MCP server ships behind the ``mcp`` extra (``pip install
"pydtsx-parser[mcp]"``); the whole module is skipped when the extra is not
installed. Tools are MCPServer-decorated plain functions, so they are called
directly and their JSON string results asserted.

Skipping is a convenience for contributors who install without the extra. CI
installs it and sets ``REQUIRE_MCP_EXTRA=1``, which turns a missing extra into
an error — otherwise a broken install would silently leave this module untested
while the run stayed green.
"""

import asyncio
import importlib
import json
import os
from pathlib import Path

import pytest

if os.environ.get("REQUIRE_MCP_EXTRA") == "1":
    importlib.import_module("mcp")
else:
    pytest.importorskip("mcp", reason="the 'mcp' optional extra is not installed")

from pydtsx_parser import mcp_server
from pydtsx_parser.constants import NAMESPACES

from .fixtures_real_world import SSIS_EXAMPLES_DIR

DTS_NS = NAMESPACES["DTS"]

EXPECTED_TOOLS = {
    "parse_dtsx_file",
    "parse_ssis_directory",
    "get_package_summary",
    "get_sql_code",
    "get_data_lineage",
    "get_data_flows",
}

_MINIMAL_PACKAGE = """<?xml version="1.0"?>
<DTS:Executable xmlns:DTS="__DTS_NS__"
  DTS:refId="Package"
  DTS:CreationName="Microsoft.Package"
  DTS:CreatorComputerName="DEVBOX01"
  DTS:CreatorName="EXAMPLE\\etl_user"
  DTS:DTSID="{12345678-1234-1234-1234-123456789012}"
  DTS:ExecutableType="Microsoft.Package"
  DTS:ObjectName="Package"
  DTS:VersionGUID="{87654321-4321-4321-4321-210987654321}">
  <DTS:Property DTS:Name="PackageFormatVersion">8</DTS:Property>
  <DTS:Variables>
    <DTS:Variable DTS:ObjectName="Var1" DTS:Namespace="User">
      <DTS:VariableValue DTS:DataType="8">value1</DTS:VariableValue>
    </DTS:Variable>
  </DTS:Variables>
  <DTS:ConnectionManagers>
    <DTS:ConnectionManager
      DTS:refId="Package.ConnectionManagers[DB]"
      DTS:CreationName="OLEDB"
      DTS:DTSID="{11111111-2222-3333-4444-555555555555}"
      DTS:ObjectName="DB">
      <DTS:ObjectData>
        <DTS:ConnectionManager
          DTS:ConnectionString="Data Source=SQLSRV01;Initial Catalog=SALESDB;Integrated Security=SSPI;" />
      </DTS:ObjectData>
    </DTS:ConnectionManager>
  </DTS:ConnectionManagers>
</DTS:Executable>""".replace("__DTS_NS__", DTS_NS)


@pytest.fixture
def package_path(tmp_path: Path) -> str:
    """A minimal valid .dtsx package on disk."""
    path = tmp_path / "Package.dtsx"
    path.write_text(_MINIMAL_PACKAGE, encoding="utf-8")
    return str(path)


def _pipeline_with_transformation() -> str:
    """A Data Flow Task with a source, a transformation, and a destination.

    None of the real-world fixtures contain a component classified as
    "transformation" (Microsoft.DerivedColumn/Sort/MergeJoin/ConditionalSplit
    — see COMPONENT_CLASSIFICATION), so get_data_lineage's transformation
    branch needs a synthetic pipeline to be exercised at all.
    """
    return """
    <DTS:Executable DTS:refId="Package\\DFT One" DTS:CreationName="Microsoft.Pipeline"
        DTS:ObjectName="DFT One">
      <DTS:ObjectData>
        <pipeline>
          <components>
            <component refId="Package\\DFT One\\Src" name="OLE DB Source"
                componentClassID="Microsoft.OLEDBSource">
              <properties>
                <property name="SqlCommand">SELECT * FROM Foo</property>
              </properties>
              <outputs>
                <output refId="Package\\DFT One\\Src.Outputs[Output]" name="Output"
                    isErrorOut="false">
                  <outputColumns>
                    <outputColumn refId="Package\\DFT One\\Src.Outputs[Output].Columns[ID]"
                        name="ID" dataType="3" length="0" precision="0" scale="0"
                        codePage="0" lineageId="1" errorRowDisposition="FailComponent"
                        truncationRowDisposition="FailComponent" />
                  </outputColumns>
                </output>
              </outputs>
            </component>
            <component refId="Package\\DFT One\\DC" name="Derived Column"
                componentClassID="Microsoft.DerivedColumn">
              <inputs>
                <input refId="Package\\DFT One\\DC.Inputs[Input]" name="Input">
                  <inputColumns>
                    <inputColumn refId="Package\\DFT One\\DC.Inputs[Input].Columns[ID]"
                        cachedName="ID" cachedDataType="3" cachedLength="0"
                        cachedPrecision="0" cachedScale="0" cachedCodepage="0"
                        lineageId="1" externalMetadataColumnId="0" />
                  </inputColumns>
                </input>
              </inputs>
              <outputs>
                <output refId="Package\\DFT One\\DC.Outputs[Output]" name="Output"
                    isErrorOut="false">
                  <outputColumns>
                    <outputColumn refId="Package\\DFT One\\DC.Outputs[Output].Columns[ID]"
                        name="ID" dataType="3" length="0" precision="0" scale="0"
                        codePage="0" lineageId="2" errorRowDisposition="FailComponent"
                        truncationRowDisposition="FailComponent" />
                  </outputColumns>
                </output>
              </outputs>
            </component>
            <component refId="Package\\DFT One\\Dest" name="OLE DB Destination"
                componentClassID="Microsoft.OLEDBDestination">
              <inputs>
                <input refId="Package\\DFT One\\Dest.Inputs[Input]" name="Input">
                  <inputColumns>
                    <inputColumn refId="Package\\DFT One\\Dest.Inputs[Input].Columns[ID]"
                        cachedName="ID" cachedDataType="3" cachedLength="0"
                        cachedPrecision="0" cachedScale="0" cachedCodepage="0"
                        lineageId="2" externalMetadataColumnId="0" />
                  </inputColumns>
                </input>
              </inputs>
            </component>
          </components>
          <paths>
            <path refId="Package\\DFT One.Paths[1]" name="Output1"
                startId="Package\\DFT One\\Src.Outputs[Output]"
                endId="Package\\DFT One\\DC.Inputs[Input]" />
            <path refId="Package\\DFT One.Paths[2]" name="Output2"
                startId="Package\\DFT One\\DC.Outputs[Output]"
                endId="Package\\DFT One\\Dest.Inputs[Input]" />
          </paths>
        </pipeline>
      </DTS:ObjectData>
    </DTS:Executable>
    <DTS:Executable DTS:refId="Package\\DFT Two" DTS:CreationName="Microsoft.Pipeline"
        DTS:ObjectName="DFT Two">
      <DTS:ObjectData>
        <pipeline>
          <components></components>
        </pipeline>
      </DTS:ObjectData>
    </DTS:Executable>
    """


_TWO_PIPELINE_PACKAGE = f"""<?xml version="1.0"?>
<DTS:Executable xmlns:DTS="{DTS_NS}"
  DTS:refId="Package"
  DTS:CreationName="Microsoft.Package"
  DTS:ObjectName="Package"
  DTS:ExecutableType="Microsoft.Package">
  <DTS:Executables>
    {_pipeline_with_transformation()}
  </DTS:Executables>
</DTS:Executable>"""


@pytest.fixture
def two_pipeline_package_path(tmp_path: Path) -> str:
    """A package with two Data Flow Tasks, one containing a transformation."""
    path = tmp_path / "TwoPipelines.dtsx"
    path.write_text(_TWO_PIPELINE_PACKAGE, encoding="utf-8")
    return str(path)


class TestToolRegistration:
    def test_all_tools_registered(self):
        """Every documented tool is registered on the MCPServer instance."""
        tools = asyncio.run(mcp_server.mcp.list_tools())
        names = {tool.name for tool in tools}
        assert names >= EXPECTED_TOOLS


class TestParseDtsxFile:
    def test_returns_envelope_json(self, package_path):
        data = json.loads(mcp_server.parse_dtsx_file(package_path))
        assert data["file_type"] == "dtsx_package"
        assert "format_version" in data
        assert "redaction_summary" in data
        assert data["content"]["package_attributes"]["object_name"] == "Package"

    def test_missing_file_returns_error_json(self, tmp_path):
        data = json.loads(mcp_server.parse_dtsx_file(str(tmp_path / "missing.dtsx")))
        assert data.get("error") is True


class TestParseSsisDirectory:
    def test_parses_directory(self, package_path):
        directory = str(Path(package_path).parent)
        data = json.loads(mcp_server.parse_ssis_directory(directory))
        assert data["file_type"] == "project_directory"
        assert data["summary"]["packages"] == 1

    def test_missing_directory_returns_error_json(self, tmp_path):
        data = json.loads(mcp_server.parse_ssis_directory(str(tmp_path / "nope")))
        assert data.get("error") is True


class TestGetPackageSummary:
    def test_summarizes_package(self, package_path):
        data = json.loads(mcp_server.get_package_summary(package_path))
        assert data["package_name"] == "Package"
        assert data["connection_managers"] == [{"name": "DB", "type": "OLEDB"}]
        assert data["variable_count"] == 1
        assert data["precedence_constraint_count"] == 0
        assert "completeness" in data

    def test_missing_file_returns_error_json(self, tmp_path):
        data = json.loads(mcp_server.get_package_summary(str(tmp_path / "no.dtsx")))
        assert data.get("error") is True


class TestGetSqlCode:
    def test_no_sql_tasks_yields_empty_list(self, package_path):
        data = json.loads(mcp_server.get_sql_code(package_path))
        assert data["sql_statements"] == []
        assert data["count"] == 0


class TestGetDataLineage:
    def test_minimal_package_has_no_edges(self, package_path):
        data = json.loads(mcp_server.get_data_lineage(package_path))
        assert data["control_flow_edges"] == []
        assert data["data_flow_lineage"] == []

    def test_missing_file_returns_error_json(self, tmp_path):
        data = json.loads(mcp_server.get_data_lineage(str(tmp_path / "missing.dtsx")))
        assert data.get("error") is True

    def test_control_flow_edge_from_real_package(self):
        """Loader.dtsx has one precedence constraint: SQL task -> data flow."""
        data = json.loads(
            mcp_server.get_data_lineage(str(SSIS_EXAMPLES_DIR / "Loader.dtsx"))
        )
        assert data["control_flow_edges"] == [
            {
                "from": "Execute SQL Task",
                "to": "Data Flow Task",
                "condition": "Success",
                "eval_op": "Constraint",
            }
        ]

    def test_source_and_destination_from_real_package(self):
        """Loader.dtsx: Flat File Source -> Data Conversion -> OLE DB Destination."""
        data = json.loads(
            mcp_server.get_data_lineage(str(SSIS_EXAMPLES_DIR / "Loader.dtsx"))
        )
        flow = data["data_flow_lineage"][0]
        assert flow["task_name"] == "Data Flow Task"
        assert flow["sources"] == [
            {
                "name": "Flat File Source",
                "class_id": "Microsoft.FlatFileSource",
                "query_or_table": "",
                "output_column_count": 2,
            }
        ]
        assert flow["destinations"] == [
            {
                "name": "OLE DB Destination",
                "class_id": "Microsoft.OLEDBDestination",
                "input_column_count": 2,
            }
        ]
        assert flow["topological_order"] == [
            "Flat File Source",
            "Data Conversion",
            "OLE DB Destination",
        ]
        assert flow["path_count"] == 2

    def test_source_query_or_table_from_sql_command(self):
        """ExportColumn.dtsx's source has a SqlCommand custom property."""
        data = json.loads(
            mcp_server.get_data_lineage(str(SSIS_EXAMPLES_DIR / "ExportColumn.dtsx"))
        )
        source = data["data_flow_lineage"][0]["sources"][0]
        assert source["query_or_table"] == "[demo].[export_column]"

    def test_transformation_is_classified_and_typed(self, two_pipeline_package_path):
        data = json.loads(
            mcp_server.get_data_lineage(two_pipeline_package_path, task_name="DFT One")
        )
        assert len(data["data_flow_lineage"]) == 1
        flow = data["data_flow_lineage"][0]
        assert flow["task_name"] == "DFT One"
        assert flow["transformations"] == [
            {
                "name": "Derived Column",
                "class_id": "Microsoft.DerivedColumn",
                "type": "DerivedColumn",
            }
        ]

    def test_task_name_filters_to_matching_pipeline_only(
        self, two_pipeline_package_path
    ):
        data = json.loads(
            mcp_server.get_data_lineage(two_pipeline_package_path, task_name="DFT Two")
        )
        assert [f["task_name"] for f in data["data_flow_lineage"]] == ["DFT Two"]

    def test_no_task_name_returns_every_pipeline(self, two_pipeline_package_path):
        data = json.loads(mcp_server.get_data_lineage(two_pipeline_package_path))
        assert {f["task_name"] for f in data["data_flow_lineage"]} == {
            "DFT One",
            "DFT Two",
        }


class TestGetDataFlows:
    def test_no_pipelines_yields_empty_list(self, package_path):
        data = json.loads(mcp_server.get_data_flows(package_path))
        assert data["data_flows"] == []
        assert data["count"] == 0
