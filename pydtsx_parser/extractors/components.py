"""Data flow component extraction and classification from SSIS pipeline XML.

Extracts component elements from data flow pipelines including their metadata,
custom properties, connections, inputs, and outputs. Components are in the
default namespace (no DTS prefix) within the pipeline's ObjectData element.

Each component is classified as "source", "destination", "transformation",
or "unknown" based on its componentClassID attribute and the known
COMPONENT_CLASSIFICATION registry in constants.py.

If extraction fails for a component, it is marked as "failed" with a reason
rather than returning partial data.
"""

import xml.etree.ElementTree as ET

from pydtsx_parser.constants import COMPONENT_CLASSIFICATION
from pydtsx_parser.extractors.columns import (
    extract_external_metadata,
    extract_input_columns,
    extract_output_columns,
)
from pydtsx_parser.extractors.sort import extract_sort_details
from pydtsx_parser.extractors.sources import extract_source_config, is_source_component
from pydtsx_parser.extractors.transformations import (
    extract_derived_columns,
    extract_merge_join,
)


def extract_component(component_element: ET.Element) -> dict:
    """Extract a single data flow component with full metadata.

    Extracts all attributes, custom properties, connections, inputs (with
    input columns and external metadata), and outputs (with output columns
    and external metadata) from a <component> element.

    If any required attribute (refId, componentClassID) is missing or an
    unexpected error occurs during extraction, the component is marked as
    "failed" with a reason string.

    Args:
        component_element: An XML <component> element from a data flow pipeline.

    Returns:
        Dictionary representing the component. On success, contains keys:
        ref_id, name, component_class_id, classification, contact_info,
        version, uses_dispositions, custom_properties, connections, inputs,
        outputs. On failure, contains keys: ref_id (if available), name
        (if available), extraction_status, failure_reason.
    """
    try:
        ref_id = component_element.get("refId", "")
        name = component_element.get("name", "")
        component_class_id = component_element.get("componentClassID", "")

        if not component_class_id:
            return _failed_component(
                ref_id,
                name,
                "Missing required componentClassID attribute",
            )

        contact_info = component_element.get("contactInfo", "")
        version = component_element.get("version", "")
        uses_dispositions_raw = component_element.get("usesDispositions", "")
        uses_dispositions = uses_dispositions_raw.lower() == "true"

        classification = classify_component(component_class_id)

        custom_properties = _extract_custom_properties(component_element)
        connections = _extract_connections(component_element)
        inputs = _extract_inputs(component_element)
        outputs = _extract_outputs(component_element)

        result = {
            "ref_id": ref_id,
            "name": name,
            "component_class_id": component_class_id,
            "classification": classification,
            "contact_info": contact_info,
            "version": version,
            "uses_dispositions": uses_dispositions,
            "custom_properties": custom_properties,
            "connections": connections,
            "inputs": inputs,
            "outputs": outputs,
        }

        # Enrich with transformation-specific details
        if component_class_id == "Microsoft.DerivedColumn":
            derived_details = extract_derived_columns(component_element)
            result.update(derived_details)
        elif component_class_id == "Microsoft.Sort":
            sort_details = extract_sort_details(component_element)
            result.update(sort_details)
        elif component_class_id == "Microsoft.MergeJoin":
            merge_join_details = extract_merge_join(component_element)
            result.update(merge_join_details)

        # Enrich with source-specific details
        if is_source_component(component_class_id):
            source_config = extract_source_config(component_element)
            result["source_config"] = source_config

        return result

    except ValueError as exc:
        # ValueError from transformation extractors indicates a required
        # element is missing (e.g., Requirement 10.7 for DerivedColumn
        # overwrite with missing lineageId or Expression)
        ref_id = component_element.get("refId", "")
        name = component_element.get("name", "")
        return _failed_component(ref_id, name, str(exc))
    except Exception as exc:
        # If extraction fails for any reason, mark as failed
        ref_id = component_element.get("refId", "")
        name = component_element.get("name", "")
        return _failed_component(ref_id, name, str(exc))


def classify_component(component_class_id: str) -> str:
    """Classify a component by its componentClassID.

    Looks up the ID in the COMPONENT_CLASSIFICATION registry. Returns
    "unknown" if the ID is not found in the registry.

    Args:
        component_class_id: The componentClassID attribute value.

    Returns:
        One of "source", "destination", "transformation", or "unknown".
    """
    return COMPONENT_CLASSIFICATION.get(component_class_id, "unknown")


def _failed_component(ref_id: str, name: str, reason: str) -> dict:
    """Build a failed component dict with extraction status and reason.

    Args:
        ref_id: The component's refId attribute (may be empty).
        name: The component's name attribute (may be empty).
        reason: Human-readable explanation of why extraction failed.

    Returns:
        Dictionary with ref_id, name, extraction_status, and failure_reason.
    """
    return {
        "ref_id": ref_id,
        "name": name,
        "extraction_status": "failed",
        "failure_reason": reason,
    }


def _extract_custom_properties(component_element: ET.Element) -> list[dict]:
    """Extract custom properties from a component element.

    Looks for a <properties> child element, then extracts each <property>
    with its name attribute and text content as the value.

    Args:
        component_element: An XML <component> element.

    Returns:
        List of dicts with "name" and "value" keys.
    """
    properties_container = component_element.find("properties")
    if properties_container is None:
        return []

    results = []
    for prop_element in properties_container.findall("property"):
        prop_name = prop_element.get("name", "")
        prop_value = prop_element.text or ""
        results.append({"name": prop_name, "value": prop_value})

    return results


def _extract_connections(component_element: ET.Element) -> list[dict]:
    """Extract connection references from a component element.

    Looks for a <connections> child element, then extracts each <connection>
    with its refId and connectionManagerID attributes.

    Args:
        component_element: An XML <component> element.

    Returns:
        List of dicts with "ref_id" and "connection_manager_ref" keys.
    """
    connections_container = component_element.find("connections")
    if connections_container is None:
        return []

    results = []
    for conn_element in connections_container.findall("connection"):
        ref_id = conn_element.get("refId", "")
        connection_manager_ref = conn_element.get("connectionManagerID", "")
        results.append(
            {
                "ref_id": ref_id,
                "connection_manager_ref": connection_manager_ref,
            }
        )

    return results


def _extract_inputs(component_element: ET.Element) -> list[dict]:
    """Extract input elements from a component.

    Looks for an <inputs> child element, then extracts each <input> with
    its refId, name, input columns, and external metadata columns.

    Args:
        component_element: An XML <component> element.

    Returns:
        List of dicts, each representing an input with keys: ref_id, name,
        input_columns, external_metadata_columns.
    """
    inputs_container = component_element.find("inputs")
    if inputs_container is None:
        return []

    results = []
    for input_element in inputs_container.findall("input"):
        ref_id = input_element.get("refId", "")
        name = input_element.get("name", "")
        input_columns = extract_input_columns(input_element)
        external_metadata = extract_external_metadata(input_element)

        results.append(
            {
                "ref_id": ref_id,
                "name": name,
                "input_columns": input_columns,
                "external_metadata_columns": external_metadata,
            }
        )

    return results


def _extract_outputs(component_element: ET.Element) -> list[dict]:
    """Extract output elements from a component.

    Looks for an <outputs> child element, then extracts each <output> with
    its refId, name, isErrorOut flag, output columns, and external metadata
    columns.

    Args:
        component_element: An XML <component> element.

    Returns:
        List of dicts, each representing an output with keys: ref_id, name,
        is_error_out, output_columns, external_metadata_columns.
    """
    outputs_container = component_element.find("outputs")
    if outputs_container is None:
        return []

    results = []
    for output_element in outputs_container.findall("output"):
        ref_id = output_element.get("refId", "")
        name = output_element.get("name", "")
        is_error_out_raw = output_element.get("isErrorOut", "")
        is_error_out = is_error_out_raw.lower() == "true"
        output_columns = extract_output_columns(output_element)
        external_metadata = extract_external_metadata(output_element)

        results.append(
            {
                "ref_id": ref_id,
                "name": name,
                "is_error_out": is_error_out,
                "output_columns": output_columns,
                "external_metadata_columns": external_metadata,
            }
        )

    return results
