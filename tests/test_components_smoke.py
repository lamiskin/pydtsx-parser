"""Smoke test for component extraction and classification."""

import xml.etree.ElementTree as ET

from pydtsx_parser.extractors.components import classify_component, extract_component


def test_classify_known_source():
    assert classify_component("Microsoft.OLEDBSource") == "source"
    assert classify_component("Microsoft.FlatFileSource") == "source"
    assert classify_component("Microsoft.SSISOracleSrc") == "source"


def test_classify_known_destination():
    assert classify_component("Microsoft.OLEDBDestination") == "destination"
    assert classify_component("Microsoft.FlatFileDestination") == "destination"


def test_classify_known_transformation():
    assert classify_component("Microsoft.DerivedColumn") == "transformation"
    assert classify_component("Microsoft.Sort") == "transformation"
    assert classify_component("Microsoft.MergeJoin") == "transformation"
    assert classify_component("Microsoft.ConditionalSplit") == "transformation"


def test_classify_unknown_fallback():
    assert classify_component("SomeUnknown.Component") == "unknown"
    assert classify_component("") == "unknown"


def test_extract_full_component():
    xml_str = (
        '<component refId="Package\\DFT\\OraSource" name="Oracle Source"'
        ' componentClassID="Microsoft.SSISOracleSrc" contactInfo="Oracle Source Info"'
        ' version="1" usesDispositions="true">'
        "  <properties>"
        '    <property name="SqlCommand">SELECT * FROM PROJECTS</property>'
        '    <property name="AccessMode">0</property>'
        "  </properties>"
        "  <connections>"
        '    <connection refId="Package\\DFT\\OraSource.Connections[OracleConn]"'
        '        connectionManagerID="Package.ConnectionManagers[DB]" />'
        "  </connections>"
        "  <inputs>"
        '    <input refId="Package\\DFT\\OraSource.Inputs[Input]" name="Component Input">'
        "      <inputColumns>"
        '        <inputColumn refId="col1" cachedName="PROJECT_ID" cachedDataType="131"'
        '            cachedLength="0" cachedPrecision="10" cachedScale="0"'
        '            cachedCodepage="0" lineageId="42" externalMetadataColumnId="105" />'
        "      </inputColumns>"
        "      <externalMetadataColumns>"
        '        <externalMetadataColumn refId="ext1" name="PROJECT_ID" dataType="131"'
        '            length="0" precision="10" scale="0" codePage="0" />'
        "      </externalMetadataColumns>"
        "    </input>"
        "  </inputs>"
        "  <outputs>"
        '    <output refId="Package\\DFT\\OraSource.Outputs[Output]"'
        '        name="OLE DB Source Output" isErrorOut="false">'
        "      <outputColumns>"
        '        <outputColumn refId="out1" name="PROJECT_ID" dataType="131"'
        '            length="0" precision="10" scale="0" codePage="0"'
        '            lineageId="42" errorRowDisposition="FailComponent"'
        '            truncationRowDisposition="FailComponent" />'
        "      </outputColumns>"
        "    </output>"
        '    <output refId="Package\\DFT\\OraSource.Outputs[Error]"'
        '        name="Error Output" isErrorOut="true">'
        "    </output>"
        "  </outputs>"
        "</component>"
    )

    elem = ET.fromstring(xml_str)
    result = extract_component(elem)

    assert result["ref_id"] == "Package\\DFT\\OraSource"
    assert result["name"] == "Oracle Source"
    assert result["component_class_id"] == "Microsoft.SSISOracleSrc"
    assert result["classification"] == "source"
    assert result["contact_info"] == "Oracle Source Info"
    assert result["version"] == "1"
    assert result["uses_dispositions"] is True

    # Custom properties
    assert len(result["custom_properties"]) == 2
    assert result["custom_properties"][0] == {
        "name": "SqlCommand",
        "value": "SELECT * FROM PROJECTS",
    }
    assert result["custom_properties"][1] == {"name": "AccessMode", "value": "0"}

    # Connections
    assert len(result["connections"]) == 1
    assert (
        result["connections"][0]["connection_manager_ref"]
        == "Package.ConnectionManagers[DB]"
    )

    # Inputs
    assert len(result["inputs"]) == 1
    assert result["inputs"][0]["name"] == "Component Input"
    assert len(result["inputs"][0]["input_columns"]) == 1
    assert result["inputs"][0]["input_columns"][0]["lineage_id"] == "42"
    assert len(result["inputs"][0]["external_metadata_columns"]) == 1

    # Outputs
    assert len(result["outputs"]) == 2
    assert result["outputs"][0]["is_error_out"] is False
    assert result["outputs"][1]["is_error_out"] is True
    assert len(result["outputs"][0]["output_columns"]) == 1


def test_extract_component_missing_class_id():
    """Component without componentClassID is marked as failed."""
    xml_str = '<component refId="Package\\DFT\\Bad" name="Bad Component"></component>'
    elem = ET.fromstring(xml_str)
    result = extract_component(elem)

    assert result["extraction_status"] == "failed"
    assert "componentClassID" in result["failure_reason"]
    assert result["ref_id"] == "Package\\DFT\\Bad"
    assert result["name"] == "Bad Component"


def test_extract_component_no_children():
    """Component with class ID but no children extracts with empty lists."""
    xml_str = (
        '<component refId="Package\\DFT\\Minimal" name="Minimal"'
        ' componentClassID="Microsoft.Sort"></component>'
    )
    elem = ET.fromstring(xml_str)
    result = extract_component(elem)

    assert result["classification"] == "transformation"
    assert result["custom_properties"] == []
    assert result["connections"] == []
    assert result["inputs"] == []
    assert result["outputs"] == []


def test_extract_component_uses_dispositions_false():
    """usesDispositions defaults to False when not 'true'."""
    xml_str = (
        '<component refId="test" name="Test"'
        ' componentClassID="Microsoft.DerivedColumn"'
        ' usesDispositions="false"></component>'
    )
    elem = ET.fromstring(xml_str)
    result = extract_component(elem)

    assert result["uses_dispositions"] is False


def test_extract_component_uses_dispositions_missing():
    """usesDispositions defaults to False when attribute is missing."""
    xml_str = (
        '<component refId="test" name="Test"'
        ' componentClassID="Microsoft.DerivedColumn"></component>'
    )
    elem = ET.fromstring(xml_str)
    result = extract_component(elem)

    assert result["uses_dispositions"] is False
