"""DTSX package parser orchestrator.

Orchestrates the full parsing of a .dtsx package file:
XML parse → package attributes extraction → variables → connection managers
→ executables → completeness summary.

Handles optional attribute omission (no null values for missing attributes).
"""

import xml.etree.ElementTree as ET

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.extractors.connections import extract_connection_managers
from pydtsx_parser.extractors.executables import extract_executables
from pydtsx_parser.extractors.variables import extract_variables
from pydtsx_parser.xml_utils import (
    count_elements_and_attributes,
    get_all_attributes,
    get_root,
    parse_xml,
)

# Namespace URI for DTS elements/attributes
_DTS_NS = NAMESPACES["DTS"]

# Mapping of DTS attribute names to output key names for package-level attributes.
# Only attributes present in the source XML are included in the output (Req 1.8).
_PACKAGE_ATTRIBUTE_MAP = {
    "refId": "ref_id",
    "CreationDate": "creation_date",
    "CreationName": "creation_name",
    "CreatorComputerName": "creator_computer_name",
    "CreatorName": "creator_name",
    "DTSID": "dts_id",
    "ExecutableType": "executable_type",
    "LastModifiedProductVersion": "last_modified_product_version",
    "LocaleID": "locale_id",
    "ObjectName": "object_name",
    "PackageType": "package_type",
    "VersionBuild": "version_build",
    "VersionGUID": "version_guid",
}


def parse_dtsx(file_path: str) -> dict:
    """Parse a .dtsx file and return the complete structured representation.

    Orchestrates the full extraction pipeline:
    1. Parse XML (handles file not found / malformed XML errors)
    2. Extract package-level attributes from root element
    3. Extract DTS:Property child elements as properties
    4. Extract package-level variables
    5. Extract connection managers
    6. Extract executables (recursively)
    7. Compute completeness summary

    Args:
        file_path: Path to the .dtsx file to parse.

    Returns:
        Dict with keys: package_attributes, properties, variables,
        connection_managers, executables, completeness_summary.

    Raises:
        FileNotFoundError: If the file does not exist or path is null/empty.
        MalformedXMLError: If the file contains malformed XML.
    """
    # Step 1: Parse XML (raises FileNotFoundError or MalformedXMLError)
    tree = parse_xml(file_path)
    root = get_root(tree, file_path)

    # Step 2: Extract package-level attributes
    package_attributes = _extract_package_attributes(root)

    # Step 3: Extract DTS:Property child elements
    properties = _extract_properties(root)

    # Step 4: Extract package-level variables
    variables = extract_variables(root, scope="Package")

    # Step 5: Extract connection managers
    connection_managers = extract_connection_managers(root, file_path)

    # Step 6: Extract executables (recursively)
    executables = extract_executables(root)

    # Step 7: Compute completeness summary
    total_elements, total_attributes, skipped_items = count_elements_and_attributes(
        tree
    )
    completeness_summary = {
        "total_elements": total_elements,
        "total_attributes": total_attributes,
        "skipped_items": skipped_items,
    }

    return {
        "package_attributes": package_attributes,
        "properties": properties,
        "variables": variables,
        "connection_managers": connection_managers,
        "executables": executables,
        "completeness_summary": completeness_summary,
    }


def _extract_package_attributes(root: ET.Element) -> dict:
    """Extract package-level attributes from the root DTS:Executable element.

    Extracts known attributes into snake_case keys and includes a
    raw_attributes sub-object with ALL attributes for the no-data-loss
    guarantee.

    Optional attributes not present in the source XML are omitted from
    the output (Req 1.8) — no null or empty values are used.

    Args:
        root: The root XML element of the .dtsx file.

    Returns:
        Dict with known attributes in snake_case plus a raw_attributes dict.
    """
    attributes: dict = {}

    # Extract known attributes using the mapping
    for dts_attr_name, output_key in _PACKAGE_ATTRIBUTE_MAP.items():
        value = root.get(f"{{{_DTS_NS}}}{dts_attr_name}")
        if value is not None:
            attributes[output_key] = value

    # Include raw_attributes with ALL attributes (namespace-resolved)
    # for the no-data-loss guarantee
    attributes["raw_attributes"] = get_all_attributes(root)

    return attributes


def _extract_properties(root: ET.Element) -> list[dict]:
    """Extract DTS:Property child elements from the root element.

    Extracts direct DTS:Property children (e.g., PackageFormatVersion)
    as name/value pairs.

    Args:
        root: The root XML element of the .dtsx file.

    Returns:
        List of dicts with 'name' and 'value' keys.
    """
    properties = []
    for prop_elem in root.findall(f"{{{_DTS_NS}}}Property"):
        name = prop_elem.get(f"{{{_DTS_NS}}}Name", "")
        value = prop_elem.text or ""
        properties.append({"name": name, "value": value})

    return properties
