"""Sort component extraction from SSIS data flow XML.

Extracts sort-specific configuration from Microsoft.Sort components including
sort columns (name, sort key position, sort order, comparison flags) and the
EliminateDuplicates property.

Sort columns are identified by a non-zero SortKeyPosition property on output
columns. Positive values indicate ascending order, negative values indicate
descending order. The absolute value represents the sort priority (1 = first
sort key, 2 = second, etc.). Columns with SortKeyPosition=0 are pass-through
columns and are not included in the sort column list.
"""

import xml.etree.ElementTree as ET


def extract_sort_details(component_element: ET.Element) -> dict:
    """Extract sort-specific details from a Microsoft.Sort component element.

    Extracts:
    - eliminate_duplicates: Whether the sort removes duplicate rows
    - sort_columns: List of sort key columns with position, order, and flags

    Args:
        component_element: An XML <component> element with
            componentClassID="Microsoft.Sort".

    Returns:
        Dictionary with keys:
        - eliminate_duplicates (bool): True if EliminateDuplicates property is "1"
        - sort_columns (list[dict]): List of sort column dicts, each with keys:
            name, sort_key_position, sort_order, comparison_flags
    """
    eliminate_duplicates = _extract_eliminate_duplicates(component_element)
    sort_columns = _extract_sort_columns(component_element)

    return {
        "eliminate_duplicates": eliminate_duplicates,
        "sort_columns": sort_columns,
    }


def _extract_eliminate_duplicates(component_element: ET.Element) -> bool:
    """Extract the EliminateDuplicates property value from a Sort component.

    Looks for a <property name="EliminateDuplicates"> element in the
    component's <properties> container.

    Args:
        component_element: An XML <component> element.

    Returns:
        True if the property value is "1", False otherwise (including when
        the property is missing).
    """
    properties_container = component_element.find("properties")
    if properties_container is None:
        return False

    for prop_element in properties_container.findall("property"):
        if prop_element.get("name") == "EliminateDuplicates":
            return (prop_element.text or "").strip() == "1"

    return False


def _extract_sort_columns(component_element: ET.Element) -> list[dict]:
    """Extract sort key columns from a Sort component's output columns.

    Iterates over output columns in non-error outputs and identifies those
    with a non-zero SortKeyPosition property. For each sort key column,
    extracts:
    - name: The column's name attribute
    - sort_key_position: Absolute value of SortKeyPosition (priority)
    - sort_order: "ascending" if positive, "descending" if negative
    - comparison_flags: The ComparisonFlags property value as a string

    Args:
        component_element: An XML <component> element.

    Returns:
        List of sort column dicts sorted by sort_key_position. Returns
        empty list if no sort key columns are found.
    """
    sort_columns: list[dict] = []

    outputs_container = component_element.find("outputs")
    if outputs_container is None:
        return sort_columns

    for output_element in outputs_container.findall("output"):
        # Skip error outputs
        if output_element.get("isErrorOut", "").lower() == "true":
            continue

        output_columns_container = output_element.find("outputColumns")
        if output_columns_container is None:
            continue

        for col_element in output_columns_container.findall("outputColumn"):
            sort_col = _extract_sort_column_if_key(col_element)
            if sort_col is not None:
                sort_columns.append(sort_col)

    # Sort by sort_key_position for consistent ordering
    sort_columns.sort(key=lambda c: c["sort_key_position"])

    return sort_columns


def _extract_sort_column_if_key(col_element: ET.Element) -> dict | None:
    """Extract sort column info from an output column if it's a sort key.

    A column is a sort key if its SortKeyPosition property is non-zero.

    Args:
        col_element: An <outputColumn> XML element.

    Returns:
        Dictionary with sort column details if it's a sort key, None otherwise.
    """
    properties_container = col_element.find("properties")
    if properties_container is None:
        return None

    sort_key_position_raw = None
    comparison_flags = "0"

    for prop_element in properties_container.findall("property"):
        prop_name = prop_element.get("name", "")
        if prop_name == "SortKeyPosition":
            sort_key_position_raw = (prop_element.text or "").strip()
        elif prop_name == "ComparisonFlags":
            comparison_flags = (prop_element.text or "0").strip()

    if sort_key_position_raw is None:
        return None

    try:
        sort_key_position_int = int(sort_key_position_raw)
    except (ValueError, TypeError):
        return None

    # SortKeyPosition=0 means pass-through column, not a sort key
    if sort_key_position_int == 0:
        return None

    sort_order = "ascending" if sort_key_position_int > 0 else "descending"
    sort_key_position = abs(sort_key_position_int)

    return {
        "name": col_element.get("name", ""),
        "sort_key_position": sort_key_position,
        "sort_order": sort_order,
        "comparison_flags": comparison_flags,
    }
