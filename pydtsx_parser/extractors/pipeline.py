"""Data flow pipeline extraction orchestrator for SSIS Microsoft.Pipeline executables.

Combines component extraction, path extraction, topological ordering, and
error output extraction for data flow tasks. The pipeline element lives inside
the executable's DTS:ObjectData → pipeline → components structure.

Pipeline child elements (pipeline, components, component, paths, path) are in
the default namespace (no DTS prefix), while the ObjectData wrapper uses the
DTS namespace.
"""

import xml.etree.ElementTree as ET

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.extractors.components import extract_component
from pydtsx_parser.extractors.paths import compute_topological_order, extract_paths

_DTS_NS = NAMESPACES["DTS"]


def extract_pipeline(executable_element: ET.Element) -> dict:
    """Extract all data flow components, paths, and ordering from a pipeline task.

    Navigates from the DTS:Executable element down through DTS:ObjectData →
    pipeline → components to find all component elements. Also extracts paths
    from the pipeline element and computes topological ordering.

    Error outputs are gathered from components that have outputs with
    is_error_out set to True.

    Args:
        executable_element: The DTS:Executable XML element that contains
            a Microsoft.Pipeline task.

    Returns:
        Dict with keys: components, paths, topological_order, error_outputs.
        Returns empty lists for all keys if the pipeline structure cannot be found.
    """
    empty_result: dict[str, list] = {
        "components": [],
        "paths": [],
        "topological_order": [],
        "error_outputs": [],
    }

    # Navigate: DTS:ObjectData → pipeline → components
    object_data = executable_element.find(f"{{{_DTS_NS}}}ObjectData")
    if object_data is None:
        return empty_result

    pipeline_element = object_data.find("pipeline")
    if pipeline_element is None:
        return empty_result

    # Extract components
    components_container = pipeline_element.find("components")
    components = []
    if components_container is not None:
        for component_element in components_container.findall("component"):
            component = extract_component(component_element)
            components.append(component)

    # Extract paths from the pipeline element
    paths = extract_paths(pipeline_element)

    # Compute topological order
    topological_order = compute_topological_order(components, paths)

    # Gather error outputs from components
    error_outputs = _gather_error_outputs(components)

    return {
        "components": components,
        "paths": paths,
        "topological_order": topological_order,
        "error_outputs": error_outputs,
    }


def _gather_error_outputs(components: list[dict]) -> list[dict]:
    """Gather error output information from all components.

    Iterates through each component's outputs and collects those where
    is_error_out is True, building a summary with the component context.

    Args:
        components: List of extracted component dicts.

    Returns:
        List of error output dicts with keys: component_name,
        component_ref_id, output_ref_id, output_name, output_columns.
    """
    error_outputs = []

    for component in components:
        # Skip failed components that don't have outputs
        if component.get("extraction_status") == "failed":
            continue

        comp_name = component.get("name", "")
        comp_ref_id = component.get("ref_id", "")

        for output in component.get("outputs", []):
            if output.get("is_error_out", False):
                error_outputs.append(
                    {
                        "component_name": comp_name,
                        "component_ref_id": comp_ref_id,
                        "output_ref_id": output.get("ref_id", ""),
                        "output_name": output.get("name", ""),
                        "output_columns": output.get("output_columns", []),
                    }
                )

    return error_outputs
