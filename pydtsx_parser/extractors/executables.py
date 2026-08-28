"""Recursive executable extraction from DTS:Executables elements.

Extracts all executable tasks from SSIS packages including their type,
name, identifiers, disabled state, description, properties, variables,
and child executables (recursively).
"""

import xml.etree.ElementTree as ET

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.extractors.variables import extract_variables

DTS_NS = NAMESPACES["DTS"]


def extract_executables(parent_element: ET.Element) -> list[dict]:
    """Recursively extract all DTS:Executable elements from a parent element.

    Looks for a DTS:Executables child element and extracts each DTS:Executable
    within it. For each executable, extracts attributes, properties, variables,
    and recursively processes any nested child executables.

    Args:
        parent_element: The XML element containing a DTS:Executables child
            (typically the package root or another executable element).

    Returns:
        List of executable dicts. Returns empty list if no DTS:Executables
        element exists or it is empty.
    """
    executables_elem = parent_element.find(f"{{{DTS_NS}}}Executables")
    if executables_elem is None:
        return []

    results = []
    for exec_elem in executables_elem.findall(f"{{{DTS_NS}}}Executable"):
        executable = _extract_single_executable(exec_elem)
        results.append(executable)

    return results


def _extract_single_executable(exec_elem: ET.Element) -> dict:
    """Extract a single DTS:Executable element into a dict.

    Extracts all required attributes, DTS:Property children, task-level
    variables, and recursively extracts child executables.

    Args:
        exec_elem: The DTS:Executable XML element.

    Returns:
        Dict with executable properties. Optional attributes that are not
        present in the source XML are omitted from the dict (per Req 1.8).
    """
    executable: dict = {}

    # Required/common attributes
    ref_id = exec_elem.get(f"{{{DTS_NS}}}refId")
    if ref_id is not None:
        executable["ref_id"] = ref_id

    creation_name = exec_elem.get(f"{{{DTS_NS}}}CreationName")
    if creation_name is not None:
        executable["creation_name"] = creation_name
        executable["executable_type"] = creation_name

    object_name = exec_elem.get(f"{{{DTS_NS}}}ObjectName")
    if object_name is not None:
        executable["object_name"] = object_name

    dts_id = exec_elem.get(f"{{{DTS_NS}}}DTSID")
    if dts_id is not None:
        executable["dts_id"] = dts_id

    # Disabled flag - convert string to Python bool, default False
    disabled_str = exec_elem.get(f"{{{DTS_NS}}}Disabled")
    if disabled_str is not None:
        executable["disabled"] = disabled_str.lower() == "true"
    else:
        executable["disabled"] = False

    # Optional: Description (omit if not present per Req 1.8)
    description = exec_elem.get(f"{{{DTS_NS}}}Description")
    if description is not None:
        executable["description"] = description

    # Extract DTS:Property child elements
    executable["properties"] = _extract_properties(exec_elem)

    # Extract task-level variables
    executable["variables"] = extract_variables(exec_elem)

    # Recursively extract child executables
    executable["child_executables"] = extract_executables(exec_elem)

    return executable


def _extract_properties(exec_elem: ET.Element) -> list[dict]:
    """Extract DTS:Property child elements from an executable.

    Extracts only direct DTS:Property children (not those nested in
    sub-elements like ObjectData).

    Args:
        exec_elem: The DTS:Executable XML element.

    Returns:
        List of property dicts with 'name' and 'value' keys.
    """
    properties = []
    for prop_elem in exec_elem.findall(f"{{{DTS_NS}}}Property"):
        name = prop_elem.get(f"{{{DTS_NS}}}Name", "")
        value = prop_elem.text or ""
        properties.append({"name": name, "value": value})

    return properties
