"""Connection manager extraction from SSIS package XML.

Extracts DTS:ConnectionManager elements from DTS:ConnectionManagers containers
with type-specific handling for FLATFILE, OLEDB, ADO.NET:SQL, ORACLE, and
unknown connection manager types.

Each connection manager type has distinct ObjectData properties:
- FLATFILE: format, delimiters, code page, columns with type/delimiter/width
- OLEDB / ADO.NET:SQL: connection string preserving all key-value pairs
- ORACLE: server, username, Oracle home paths, authentication flags
- Unknown: all ObjectData properties extracted generically
"""

import xml.etree.ElementTree as ET

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.errors import ExtractionError

# Namespace URI used for qualified element/attribute lookups
_DTS_NS = NAMESPACES["DTS"]


def extract_connection_managers(
    parent_element: ET.Element, file_path: str = ""
) -> list[dict]:
    """Extract all connection managers from a parent element.

    Looks for a DTS:ConnectionManagers child element, then extracts each
    DTS:ConnectionManager with common attributes and type-specific properties.

    Args:
        parent_element: The XML element containing a DTS:ConnectionManagers child.
        file_path: Source file path for error reporting.

    Returns:
        List of connection manager dicts.

    Raises:
        ExtractionError: If a connection manager is missing the ObjectName attribute.
    """
    conn_managers_container = parent_element.find(f"{{{_DTS_NS}}}ConnectionManagers")
    if conn_managers_container is None:
        return []

    results = []
    for cm_element in conn_managers_container.findall(
        f"{{{_DTS_NS}}}ConnectionManager"
    ):
        cm = extract_single_connection_manager(cm_element, file_path)
        results.append(cm)

    return results


def extract_single_connection_manager(
    cm_element: ET.Element, file_path: str = ""
) -> dict:
    """Extract a single DTS:ConnectionManager element into a dictionary.

    Extracts common fields (refId, ObjectName, DTSID, CreationName, Description)
    and dispatches to type-specific extraction based on CreationName.

    Args:
        cm_element: A DTS:ConnectionManager XML element.
        file_path: Source file path for error reporting.

    Returns:
        Dictionary with connection manager data.

    Raises:
        ExtractionError: If the ObjectName attribute is missing.
    """
    # Extract common attributes
    ref_id = cm_element.get(f"{{{_DTS_NS}}}refId", "")
    object_name = cm_element.get(f"{{{_DTS_NS}}}ObjectName")
    dts_id = cm_element.get(f"{{{_DTS_NS}}}DTSID", "")
    creation_name = cm_element.get(f"{{{_DTS_NS}}}CreationName", "")
    description = cm_element.get(f"{{{_DTS_NS}}}Description", "")

    # Requirement 3.7: Missing ObjectName fails extraction entirely
    if object_name is None:
        raise ExtractionError(
            file_path,
            "Connection manager element is missing required DTS:ObjectName attribute",
        )

    result: dict = {
        "ref_id": ref_id,
        "object_name": object_name,
        "dts_id": dts_id,
        "creation_name": creation_name,
    }

    # Only include description if present (non-empty)
    if description:
        result["description"] = description

    # Find the ObjectData container and inner ConnectionManager element
    object_data = cm_element.find(f"{{{_DTS_NS}}}ObjectData")
    if object_data is None:
        result["properties"] = {}
        return result

    inner_cm = object_data.find(f"{{{_DTS_NS}}}ConnectionManager")
    if inner_cm is None:
        result["properties"] = {}
        return result

    # Dispatch based on creation name
    creation_name_upper = creation_name.upper()
    if creation_name_upper == "FLATFILE":
        result["properties"] = _extract_flatfile_properties(inner_cm)
    elif creation_name_upper in ("OLEDB", "ADO.NET:SQL"):
        result["properties"] = _extract_oledb_properties(inner_cm)
    elif creation_name_upper == "ORACLE":
        result["properties"] = _extract_oracle_properties(inner_cm)
    else:
        result["properties"] = _extract_unknown_properties(inner_cm)

    return result


def _extract_flatfile_properties(inner_cm: ET.Element) -> dict:
    """Extract FLATFILE connection manager properties.

    Extracts format, locale ID, delimiters, column settings, code page,
    connection string (file path), and FlatFileColumns with per-column metadata.

    Args:
        inner_cm: The inner DTS:ConnectionManager element within ObjectData.

    Returns:
        Dictionary with flat file specific properties.
    """
    props: dict = {}

    # Extract attributes from the inner ConnectionManager element
    fmt = inner_cm.get(f"{{{_DTS_NS}}}Format", "")
    if fmt:
        props["format"] = fmt

    locale_id = inner_cm.get(f"{{{_DTS_NS}}}LocaleID", "")
    if locale_id:
        props["locale_id"] = locale_id

    header_row_delimiter = inner_cm.get(f"{{{_DTS_NS}}}HeaderRowDelimiter", "")
    if header_row_delimiter:
        props["header_row_delimiter"] = header_row_delimiter

    col_names_in_first_row = inner_cm.get(f"{{{_DTS_NS}}}ColumnNamesInFirstDataRow", "")
    if col_names_in_first_row:
        props["column_names_in_first_data_row"] = col_names_in_first_row == "True"

    header_rows_to_skip = inner_cm.get(f"{{{_DTS_NS}}}HeaderRowsToSkip", "")
    if header_rows_to_skip:
        props["header_rows_to_skip"] = int(header_rows_to_skip)

    row_delimiter = inner_cm.get(f"{{{_DTS_NS}}}RowDelimiter", "")
    # Include even if empty since RowDelimiter="" is meaningful
    props["row_delimiter"] = row_delimiter

    text_qualifier = inner_cm.get(f"{{{_DTS_NS}}}TextQualifier", "")
    if text_qualifier:
        props["text_qualifier"] = text_qualifier

    code_page = inner_cm.get(f"{{{_DTS_NS}}}CodePage", "")
    if code_page:
        props["code_page"] = code_page

    connection_string = inner_cm.get(f"{{{_DTS_NS}}}ConnectionString", "")
    if connection_string:
        props["connection_string"] = connection_string

    # Extract FlatFileColumns
    columns_container = inner_cm.find(f"{{{_DTS_NS}}}FlatFileColumns")
    if columns_container is not None:
        columns = []
        for col_element in columns_container.findall(f"{{{_DTS_NS}}}FlatFileColumn"):
            column = _extract_flat_file_column(col_element)
            columns.append(column)
        props["flat_file_columns"] = columns

    return props


def _extract_flat_file_column(col_element: ET.Element) -> dict:
    """Extract a single FlatFileColumn element.

    Args:
        col_element: A DTS:FlatFileColumn XML element.

    Returns:
        Dictionary with column metadata.
    """
    column: dict = {}

    object_name = col_element.get(f"{{{_DTS_NS}}}ObjectName", "")
    if object_name:
        column["object_name"] = object_name

    column_type = col_element.get(f"{{{_DTS_NS}}}ColumnType", "")
    if column_type:
        column["column_type"] = column_type

    column_delimiter = col_element.get(f"{{{_DTS_NS}}}ColumnDelimiter", "")
    if column_delimiter:
        column["column_delimiter"] = column_delimiter

    data_type = col_element.get(f"{{{_DTS_NS}}}DataType", "")
    if data_type:
        column["data_type"] = data_type

    max_width = col_element.get(f"{{{_DTS_NS}}}MaximumWidth", "")
    if max_width:
        column["maximum_width"] = max_width

    text_qualified = col_element.get(f"{{{_DTS_NS}}}TextQualified", "")
    if text_qualified:
        column["text_qualified"] = text_qualified == "True"

    dts_id = col_element.get(f"{{{_DTS_NS}}}DTSID", "")
    if dts_id:
        column["dts_id"] = dts_id

    return column


def _extract_oledb_properties(inner_cm: ET.Element) -> dict:
    """Extract OLEDB or ADO.NET:SQL connection manager properties.

    The connection string is stored as the DTS:ConnectionString attribute
    on the inner ConnectionManager element. All key-value pairs are preserved.

    Args:
        inner_cm: The inner DTS:ConnectionManager element within ObjectData.

    Returns:
        Dictionary with the full connection string.
    """
    props: dict = {}

    connection_string = inner_cm.get(f"{{{_DTS_NS}}}ConnectionString", "")
    if connection_string:
        props["connection_string"] = connection_string

    return props


def _extract_oracle_properties(inner_cm: ET.Element) -> dict:
    """Extract ORACLE connection manager properties.

    Oracle properties are stored as child elements (not attributes) within
    the inner ConnectionManager element. Each property is a separate element
    like <OraServerName>, <OraUserName>, etc.

    Args:
        inner_cm: The inner DTS:ConnectionManager element within ObjectData.

    Returns:
        Dictionary with Oracle-specific properties.
    """
    props: dict = {}

    # Map of Oracle child element tags to output property names
    oracle_field_map = {
        "OraServerName": "server_name",
        "OraUserName": "user_name",
        "OraPassword": "password",
        "OraOracleHome": "oracle_home",
        "OraOracleHome64": "oracle_home_64",
        "OraWinAuthentication": "win_authentication",
        "OraRetain": "retain",
        "OraInitialCatalog": "initial_catalog",
        "OraConnectionString": "connection_string",
        "OraEnableDetailedTracing": "enable_detailed_tracing",
    }

    # Boolean fields that should be converted from "True"/"False" strings
    boolean_fields = {
        "OraWinAuthentication",
        "OraRetain",
        "OraEnableDetailedTracing",
    }

    for element_tag, prop_name in oracle_field_map.items():
        child = inner_cm.find(element_tag)
        if child is not None:
            # Check if this element has Sensitive="1" attribute
            sensitive = child.get("Sensitive", "0") == "1"
            text_value = child.text or ""

            if sensitive:
                props[prop_name] = {"value": text_value, "sensitive": True}
            elif element_tag in boolean_fields:
                props[prop_name] = text_value.lower() == "true"
            else:
                props[prop_name] = text_value

    return props


def _extract_unknown_properties(inner_cm: ET.Element) -> dict:
    """Extract all properties from an unknown connection manager type.

    Extracts all attributes from the inner ConnectionManager element and
    all child element text values generically.

    Args:
        inner_cm: The inner DTS:ConnectionManager element within ObjectData.

    Returns:
        Dictionary with all discovered properties.
    """
    props: dict = {}

    # Extract all attributes from the inner element
    for attr_name, attr_value in inner_cm.attrib.items():
        # Strip namespace from attribute name for cleaner keys
        clean_name = _strip_ns_from_attr(attr_name)
        props[clean_name] = attr_value

    # Extract all child element text values
    for child in inner_cm:
        tag = child.tag
        # Strip namespace from tag
        if tag.startswith("{"):
            closing_brace = tag.index("}")
            tag = tag[closing_brace + 1 :]
        text_value = child.text or ""
        props[tag] = text_value

    return props


def _strip_ns_from_attr(attr_name: str) -> str:
    """Strip namespace URI prefix from an attribute name.

    Converts "{http://namespace.uri}LocalName" to "LocalName".

    Args:
        attr_name: An attribute name, potentially with a namespace URI prefix.

    Returns:
        The local name portion without any namespace URI.
    """
    if attr_name.startswith("{"):
        closing_brace = attr_name.index("}")
        return attr_name[closing_brace + 1 :]
    return attr_name
