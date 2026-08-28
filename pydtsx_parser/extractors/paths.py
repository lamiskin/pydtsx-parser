"""Data flow path extraction and topological ordering from SSIS pipeline XML.

Extracts path elements from the <paths> container within a pipeline element.
Each path connects a source component's output to a destination component's
input, forming a directed graph of data flow.

The topological sort uses Kahn's algorithm to derive a valid execution order
from the path edges — sources first, then transformations, then destinations.
"""

import xml.etree.ElementTree as ET
from collections import deque


def extract_paths(pipeline_element: ET.Element) -> list[dict]:
    """Extract path elements from a pipeline element.

    Looks for a <paths> child element within the pipeline, then extracts
    each <path> element with its refId, name, startId, and endId attributes.

    Args:
        pipeline_element: An XML <pipeline> element from a data flow task's
            ObjectData section.

    Returns:
        List of dicts, each representing a data flow path with keys:
        ref_id, name, start_id, end_id.
    """
    paths_container = pipeline_element.find("paths")
    if paths_container is None:
        return []

    results = []
    for path_element in paths_container.findall("path"):
        path = _extract_single_path(path_element)
        results.append(path)

    return results


def compute_topological_order(components: list[dict], paths: list[dict]) -> list[str]:
    """Derive execution order from path connections using Kahn's algorithm.

    Builds a directed graph from path edges by mapping startId/endId back
    to component names. A startId references a component's output refId,
    and an endId references a component's input refId. The parent component
    is identified by matching these refIds against component inputs/outputs.

    Args:
        components: List of component dicts (each with at minimum "name",
            "ref_id", "inputs" and "outputs" keys).
        paths: List of path dicts (each with "start_id" and "end_id").

    Returns:
        List of component names in topological order. If no paths exist,
        returns the component names in their original order.
    """
    if not components:
        return []

    if not paths:
        return [comp["name"] for comp in components]

    # Build mappings from output/input refIds to component names
    output_ref_to_component = {}
    input_ref_to_component = {}

    for comp in components:
        comp_name = comp["name"]
        for output in comp.get("outputs", []):
            output_ref_to_component[output["ref_id"]] = comp_name
        for inp in comp.get("inputs", []):
            input_ref_to_component[inp["ref_id"]] = comp_name

    # Build adjacency list and in-degree count
    all_component_names = [comp["name"] for comp in components]
    in_degree: dict[str, int] = dict.fromkeys(all_component_names, 0)
    adjacency: dict[str, list[str]] = {name: [] for name in all_component_names}

    for path in paths:
        start_id = path["start_id"]
        end_id = path["end_id"]

        source_component = output_ref_to_component.get(start_id)
        dest_component = input_ref_to_component.get(end_id)

        if source_component and dest_component and source_component != dest_component:
            adjacency[source_component].append(dest_component)
            in_degree[dest_component] += 1

    # Kahn's algorithm: start with nodes that have no incoming edges
    queue: deque[str] = deque()
    for name in all_component_names:
        if in_degree[name] == 0:
            queue.append(name)

    topological_order: list[str] = []

    while queue:
        node = queue.popleft()
        topological_order.append(node)

        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # If not all components are in the order (cycle or disconnected),
    # append any remaining components
    if len(topological_order) < len(all_component_names):
        ordered_set = set(topological_order)
        for name in all_component_names:
            if name not in ordered_set:
                topological_order.append(name)

    return topological_order


def _extract_single_path(path_element: ET.Element) -> dict:
    """Extract a single path element into a dictionary.

    Args:
        path_element: A <path> XML element from the paths container.

    Returns:
        Dictionary with path metadata: ref_id, name, start_id, end_id.
    """
    return {
        "ref_id": path_element.get("refId", ""),
        "name": path_element.get("name", ""),
        "start_id": path_element.get("startId", ""),
        "end_id": path_element.get("endId", ""),
    }
