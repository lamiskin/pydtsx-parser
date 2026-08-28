"""Smoke tests for pipeline extraction orchestrator."""

import xml.etree.ElementTree as ET

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.extractors.pipeline import extract_pipeline

DTS_NS = NAMESPACES["DTS"]


def _build_executable_xml(pipeline_content: str) -> ET.Element:
    """Helper to build a DTS:Executable element wrapping pipeline content."""
    xml_str = (
        f'<DTS:Executable xmlns:DTS="{DTS_NS}"'
        f' DTS:refId="Package\\\\DFT"'
        f' DTS:CreationName="Microsoft.Pipeline"'
        f' DTS:ObjectName="Data Flow Task">'
        f"  <DTS:ObjectData>"
        f"    <pipeline>"
        f"      {pipeline_content}"
        f"    </pipeline>"
        f"  </DTS:ObjectData>"
        f"</DTS:Executable>"
    )
    return ET.fromstring(xml_str)


def _build_component_xml(
    ref_id: str,
    name: str,
    class_id: str,
    outputs: str = "",
    inputs: str = "",
) -> str:
    """Helper to build a component XML string."""
    return (
        f'<component refId="{ref_id}" name="{name}"'
        f' componentClassID="{class_id}">'
        f"  {inputs}"
        f"  {outputs}"
        f"</component>"
    )


class TestExtractPipelineTwoComponents:
    """Test pipeline with 2 components (source → destination) connected by a path."""

    def setup_method(self):
        source_outputs = (
            "<outputs>"
            '  <output refId="Package\\DFT\\Src.Outputs[Output]"'
            '      name="OLE DB Source Output" isErrorOut="false">'
            "    <outputColumns>"
            '      <outputColumn refId="Package\\DFT\\Src.Outputs[Output].Columns[ID]"'
            '          name="ID" dataType="3" length="0" precision="0"'
            '          scale="0" codePage="0" lineageId="10"'
            '          errorRowDisposition="FailComponent"'
            '          truncationRowDisposition="FailComponent" />'
            "    </outputColumns>"
            "  </output>"
            "</outputs>"
        )
        dest_inputs = (
            "<inputs>"
            '  <input refId="Package\\DFT\\Dest.Inputs[Input]" name="OLE DB Destination Input">'
            "    <inputColumns>"
            '      <inputColumn refId="Package\\DFT\\Dest.Inputs[Input].Columns[ID]"'
            '          cachedName="ID" cachedDataType="3" cachedLength="0"'
            '          cachedPrecision="0" cachedScale="0" cachedCodepage="0"'
            '          lineageId="10" externalMetadataColumnId="200" />'
            "    </inputColumns>"
            "  </input>"
            "</inputs>"
        )

        source_comp = _build_component_xml(
            "Package\\DFT\\Src",
            "OLE DB Source",
            "Microsoft.OLEDBSource",
            outputs=source_outputs,
        )
        dest_comp = _build_component_xml(
            "Package\\DFT\\Dest",
            "OLE DB Destination",
            "Microsoft.OLEDBDestination",
            inputs=dest_inputs,
        )

        path_xml = (
            "<paths>"
            '  <path refId="Package\\DFT.Paths[Output]" name="Output"'
            '      startId="Package\\DFT\\Src.Outputs[Output]"'
            '      endId="Package\\DFT\\Dest.Inputs[Input]" />'
            "</paths>"
        )

        pipeline_content = (
            f"<components>{source_comp}{dest_comp}</components>{path_xml}"
        )
        self.executable = _build_executable_xml(pipeline_content)
        self.result = extract_pipeline(self.executable)

    def test_components_extracted(self):
        assert len(self.result["components"]) == 2
        assert self.result["components"][0]["name"] == "OLE DB Source"
        assert self.result["components"][1]["name"] == "OLE DB Destination"

    def test_paths_extracted(self):
        assert len(self.result["paths"]) == 1
        path = self.result["paths"][0]
        assert path["name"] == "Output"
        assert path["start_id"] == "Package\\DFT\\Src.Outputs[Output]"
        assert path["end_id"] == "Package\\DFT\\Dest.Inputs[Input]"

    def test_topological_order(self):
        order = self.result["topological_order"]
        assert len(order) == 2
        # Source must come before destination
        assert order.index("OLE DB Source") < order.index("OLE DB Destination")

    def test_no_error_outputs(self):
        assert self.result["error_outputs"] == []


class TestExtractPipelineEmpty:
    """Test empty pipeline (no components)."""

    def test_empty_components_element(self):
        executable = _build_executable_xml("<components></components>")
        result = extract_pipeline(executable)

        assert result["components"] == []
        assert result["paths"] == []
        assert result["topological_order"] == []
        assert result["error_outputs"] == []

    def test_no_components_element(self):
        """Pipeline element exists but has no components child."""
        executable = _build_executable_xml("")
        result = extract_pipeline(executable)

        assert result["components"] == []
        assert result["paths"] == []
        assert result["topological_order"] == []
        assert result["error_outputs"] == []

    def test_no_object_data(self):
        """Executable has no ObjectData element."""
        xml_str = (
            f'<DTS:Executable xmlns:DTS="{DTS_NS}"'
            f' DTS:refId="Package\\DFT"'
            f' DTS:CreationName="Microsoft.Pipeline"'
            f' DTS:ObjectName="Data Flow Task">'
            f"</DTS:Executable>"
        )
        executable = ET.fromstring(xml_str)
        result = extract_pipeline(executable)

        assert result["components"] == []
        assert result["paths"] == []
        assert result["topological_order"] == []
        assert result["error_outputs"] == []

    def test_no_pipeline_element(self):
        """ObjectData exists but has no pipeline child."""
        xml_str = (
            f'<DTS:Executable xmlns:DTS="{DTS_NS}"'
            f' DTS:refId="Package\\DFT"'
            f' DTS:CreationName="Microsoft.Pipeline"'
            f' DTS:ObjectName="Data Flow Task">'
            f"  <DTS:ObjectData>"
            f"    <otherElement />"
            f"  </DTS:ObjectData>"
            f"</DTS:Executable>"
        )
        executable = ET.fromstring(xml_str)
        result = extract_pipeline(executable)

        assert result["components"] == []
        assert result["paths"] == []
        assert result["topological_order"] == []
        assert result["error_outputs"] == []


class TestExtractPipelineErrorOutputs:
    """Test pipeline with error outputs on a component."""

    def setup_method(self):
        source_outputs = (
            "<outputs>"
            '  <output refId="Package\\DFT\\OraSource.Outputs[Output]"'
            '      name="Oracle Source Output" isErrorOut="false">'
            "    <outputColumns>"
            '      <outputColumn refId="Package\\DFT\\OraSource.Outputs[Output].Columns[ID]"'
            '          name="ID" dataType="3" length="0" precision="0"'
            '          scale="0" codePage="0" lineageId="10"'
            '          errorRowDisposition="FailComponent"'
            '          truncationRowDisposition="FailComponent" />'
            "    </outputColumns>"
            "  </output>"
            '  <output refId="Package\\DFT\\OraSource.Outputs[Error]"'
            '      name="Error Output" isErrorOut="true">'
            "    <outputColumns>"
            '      <outputColumn refId="Package\\DFT\\OraSource.Outputs[Error].Columns[ErrorCode]"'
            '          name="ErrorCode" dataType="3" length="0" precision="0"'
            '          scale="0" codePage="0" lineageId="99"'
            '          errorRowDisposition="NotUsed"'
            '          truncationRowDisposition="NotUsed" />'
            '      <outputColumn refId="Package\\DFT\\OraSource.Outputs[Error].Columns[ErrorColumn]"'
            '          name="ErrorColumn" dataType="3" length="0" precision="0"'
            '          scale="0" codePage="0" lineageId="100"'
            '          errorRowDisposition="NotUsed"'
            '          truncationRowDisposition="NotUsed" />'
            "    </outputColumns>"
            "  </output>"
            "</outputs>"
        )

        source_comp = _build_component_xml(
            "Package\\DFT\\OraSource",
            "Oracle Source",
            "Microsoft.SSISOracleSrc",
            outputs=source_outputs,
        )

        pipeline_content = f"<components>{source_comp}</components>"
        self.executable = _build_executable_xml(pipeline_content)
        self.result = extract_pipeline(self.executable)

    def test_error_outputs_extracted(self):
        assert len(self.result["error_outputs"]) == 1

    def test_error_output_component_info(self):
        error_out = self.result["error_outputs"][0]
        assert error_out["component_name"] == "Oracle Source"
        assert error_out["component_ref_id"] == "Package\\DFT\\OraSource"

    def test_error_output_ref_and_name(self):
        error_out = self.result["error_outputs"][0]
        assert error_out["output_ref_id"] == "Package\\DFT\\OraSource.Outputs[Error]"
        assert error_out["output_name"] == "Error Output"

    def test_error_output_columns(self):
        error_out = self.result["error_outputs"][0]
        assert len(error_out["output_columns"]) == 2
        assert error_out["output_columns"][0]["name"] == "ErrorCode"
        assert error_out["output_columns"][1]["name"] == "ErrorColumn"

    def test_non_error_outputs_not_included(self):
        """Only error outputs are in the error_outputs list."""
        for error_out in self.result["error_outputs"]:
            assert "Error" in error_out["output_name"]
