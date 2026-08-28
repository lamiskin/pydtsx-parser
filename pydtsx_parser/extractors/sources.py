"""Source component extraction from SSIS data flow XML.

Extracts source-specific configuration from OLEDBSource, FlatFileSource, and
SSISOracleSrc components including access mode, SQL command or table/view name,
variable-based alternatives, and connection manager references.

AccessMode values for OLEDBSource:
- 0: OpenRowset (table/view name)
- 1: OpenRowset from variable
- 2: SQL Command
- 3: SQL Command from variable

For FlatFileSource the AccessMode is typically 0.

The extraction always produces a source_config dict even if no properties are
configured, using empty string defaults rather than omitting fields.
"""

import xml.etree.ElementTree as ET

# Component class IDs that are treated as source components
SOURCE_CLASS_IDS = {
    "Microsoft.OLEDBSource",
    "Microsoft.FlatFileSource",
    "Microsoft.SSISOracleSrc",
}


def is_source_component(component_class_id: str) -> bool:
    """Check if a component class ID is a recognized source type.

    Args:
        component_class_id: The componentClassID attribute value.

    Returns:
        True if the component is a recognized source type.
    """
    return component_class_id in SOURCE_CLASS_IDS


def extract_source_config(component_element: ET.Element) -> dict:
    """Extract source-specific configuration from a source component element.

    Extracts AccessMode, SqlCommand, OpenRowset, SqlCommandVariable,
    OpenRowsetVariable from the component's custom properties, and the
    connection manager reference from the component's connections.

    All fields default to empty strings when not present.

    Args:
        component_element: An XML <component> element with a source
            componentClassID.

    Returns:
        Dictionary with keys:
        - access_mode (str): The AccessMode property value
        - sql_command (str): The SqlCommand property value
        - open_rowset (str): The OpenRowset property value
        - sql_command_variable (str): The SqlCommandVariable property value
        - open_rowset_variable (str): The OpenRowsetVariable property value
        - connection_manager_ref (str): The connectionManagerID from the
            first connection element
    """
    properties = _extract_source_properties(component_element)
    connection_manager_ref = _extract_connection_manager_ref(component_element)

    return {
        "access_mode": properties.get("AccessMode", ""),
        "sql_command": properties.get("SqlCommand", ""),
        "open_rowset": properties.get("OpenRowset", ""),
        "sql_command_variable": properties.get("SqlCommandVariable", ""),
        "open_rowset_variable": properties.get("OpenRowsetVariable", ""),
        "connection_manager_ref": connection_manager_ref,
    }


def _extract_source_properties(component_element: ET.Element) -> dict[str, str]:
    """Extract source-relevant custom properties from the component.

    Looks for the properties container and extracts only the source-relevant
    property names: AccessMode, SqlCommand, OpenRowset, SqlCommandVariable,
    OpenRowsetVariable.

    Args:
        component_element: An XML <component> element.

    Returns:
        Dictionary mapping property names to their text values.
    """
    source_property_names = {
        "AccessMode",
        "SqlCommand",
        "OpenRowset",
        "SqlCommandVariable",
        "OpenRowsetVariable",
    }

    properties_container = component_element.find("properties")
    if properties_container is None:
        return {}

    result = {}
    for prop_element in properties_container.findall("property"):
        prop_name = prop_element.get("name", "")
        if prop_name in source_property_names:
            result[prop_name] = prop_element.text or ""

    return result


def _extract_connection_manager_ref(component_element: ET.Element) -> str:
    """Extract the connection manager reference from the component's connections.

    Takes the connectionManagerID from the first connection element found.

    Args:
        component_element: An XML <component> element.

    Returns:
        The connectionManagerID string, or empty string if no connections exist.
    """
    connections_container = component_element.find("connections")
    if connections_container is None:
        return ""

    first_connection = connections_container.find("connection")
    if first_connection is None:
        return ""

    return first_connection.get("connectionManagerID", "")
