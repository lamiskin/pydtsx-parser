"""Variable extraction from SSIS package XML.

Extracts DTS:Variable elements from DTS:Variables containers at both
package level and task/container level with full metadata including
name, namespace, data type, value, and scope.
"""

import xml.etree.ElementTree as ET

from pydtsx_parser.constants import NAMESPACES

# Namespace URI used for qualified element/attribute lookups
_DTS_NS = NAMESPACES["DTS"]


def extract_variables(parent_element: ET.Element, scope: str = "Package") -> list[dict]:
    """Extract all DTS:Variable elements from a parent element.

    Looks for a DTS:Variables child element within parent_element,
    then extracts each DTS:Variable with its attributes and value.

    Args:
        parent_element: The XML element containing a DTS:Variables child.
        scope: The scope label (e.g., "Package" or the task's ObjectName).

    Returns:
        List of variable dicts with keys: name, namespace, data_type, value, scope.
        Returns an empty list if no DTS:Variables element is found or if it
        contains no variables.
    """
    # Find the DTS:Variables container element
    variables_container = parent_element.find(f"{{{_DTS_NS}}}Variables")
    if variables_container is None:
        return []

    variables = []
    for var_element in variables_container.findall(f"{{{_DTS_NS}}}Variable"):
        variable = _extract_single_variable(var_element, scope)
        variables.append(variable)

    return variables


def _extract_single_variable(var_element: ET.Element, scope: str) -> dict:
    """Extract a single DTS:Variable element into a dictionary.

    Args:
        var_element: A DTS:Variable XML element.
        scope: The scope label for this variable.

    Returns:
        Dictionary with keys: name, namespace, data_type, value, scope.
    """
    # Extract attributes from the Variable element
    name = var_element.get(f"{{{_DTS_NS}}}ObjectName", "")
    namespace = var_element.get(f"{{{_DTS_NS}}}Namespace", "")

    # Extract value and data type from the DTS:VariableValue child element
    value_element = var_element.find(f"{{{_DTS_NS}}}VariableValue")

    data_type = ""
    value = ""

    if value_element is not None:
        # The DataType attribute contains the numeric SSIS type code
        data_type = value_element.get(f"{{{_DTS_NS}}}DataType", "")
        # The text content is the variable's value
        value = value_element.text or ""

    return {
        "name": name,
        "namespace": namespace,
        "data_type": data_type,
        "value": value,
        "scope": scope,
    }
