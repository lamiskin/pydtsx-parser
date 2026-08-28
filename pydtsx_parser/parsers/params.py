"""Project.params file parser.

Parses SSIS Project.params XML files and extracts all parameter definitions
including name, data type, default value, sensitivity flag, and required flag.

Handles empty parameters (returns empty list) and malformed XML (returns error).
"""

import xml.etree.ElementTree as ET

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.xml_utils import get_root, parse_xml

# SSIS namespace URI
_SSIS_NS = NAMESPACES["SSIS"]


def parse_params(file_path: str) -> dict:
    """Parse a Project.params file and return extracted parameter definitions.

    Orchestrates the extraction pipeline:
    1. Parse XML (handles file not found / malformed XML errors)
    2. Find all SSIS:Parameter child elements
    3. Extract each parameter's properties (name, data type, value, sensitivity, required)
    4. Return structured result

    For empty parameters (self-closing or empty SSIS:Parameters root element),
    returns an empty parameters list rather than an error.

    Args:
        file_path: Path to the Project.params file to parse.

    Returns:
        Dict with key 'parameters' containing a list of parameter dicts.
        Each parameter dict has keys: name, data_type, default_value,
        sensitive, required.

    Raises:
        FileNotFoundError: If the file does not exist or path is null/empty.
        MalformedXMLError: If the file contains malformed XML.
    """
    # Step 1: Parse XML (raises FileNotFoundError or MalformedXMLError)
    tree = parse_xml(file_path)
    root = get_root(tree, file_path)

    # Step 2: Find all SSIS:Parameter child elements
    parameters = _extract_parameters(root)

    return {
        "parameters": parameters,
    }


def _extract_parameters(root: ET.Element) -> list[dict]:
    """Extract all parameter definitions from the root SSIS:Parameters element.

    Looks for SSIS:Parameter child elements and extracts their properties.
    If no parameter children are found (empty/self-closing root), returns
    an empty list.

    Args:
        root: The root XML element (SSIS:Parameters).

    Returns:
        List of parameter dicts with keys: name, data_type, default_value,
        sensitive, required.
    """
    parameters = []

    # Find all SSIS:Parameter child elements
    for param_elem in root.findall(f"{{{_SSIS_NS}}}Parameter"):
        param = _extract_single_parameter(param_elem)
        parameters.append(param)

    return parameters


def _extract_single_parameter(param_elem: ET.Element) -> dict:
    """Extract a single parameter definition from an SSIS:Parameter element.

    Reads the parameter name from the SSIS:Name attribute, then extracts
    property values from SSIS:Properties/SSIS:Property child elements.

    Args:
        param_elem: An SSIS:Parameter XML element.

    Returns:
        Dict with keys: name, data_type, default_value, sensitive, required.
    """
    # Get the parameter name from SSIS:Name attribute
    name = param_elem.get(f"{{{_SSIS_NS}}}Name", "")

    # Extract properties from SSIS:Properties/SSIS:Property children
    properties = _extract_parameter_properties(param_elem)

    return {
        "name": name,
        "data_type": properties.get("DataType", ""),
        "default_value": properties.get("Value", ""),
        "sensitive": properties.get("Sensitive", "0") == "1",
        "required": properties.get("Required", "0") == "1",
    }


def _extract_parameter_properties(param_elem: ET.Element) -> dict:
    """Extract property name-value pairs from an SSIS:Parameter element.

    Looks for SSIS:Properties/SSIS:Property child elements and returns
    a mapping of property name to text value.

    Args:
        param_elem: An SSIS:Parameter XML element.

    Returns:
        Dict mapping property names (from SSIS:Name attribute) to their
        text content values.
    """
    properties: dict[str, str] = {}

    # Find the SSIS:Properties container
    props_container = param_elem.find(f"{{{_SSIS_NS}}}Properties")
    if props_container is None:
        return properties

    # Extract each SSIS:Property
    for prop_elem in props_container.findall(f"{{{_SSIS_NS}}}Property"):
        prop_name = prop_elem.get(f"{{{_SSIS_NS}}}Name", "")
        prop_value = prop_elem.text or ""
        if prop_name:
            properties[prop_name] = prop_value

    return properties
