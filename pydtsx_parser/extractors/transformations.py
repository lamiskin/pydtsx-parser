"""Transformation-specific extraction from SSIS data flow components.

Extracts detailed configuration for recognized transformation components
(MergeJoin, DerivedColumn) beyond what the generic component extractor
provides. Each function takes a component element and returns a dictionary
with transformation-specific fields that augment the base component dict.
"""

import xml.etree.ElementTree as ET

# Join type numeric code to human-readable name mapping
JOIN_TYPE_MAP = {
    "0": "FULL",
    "1": "LEFT",
    "2": "INNER",
}


def extract_derived_columns(component_element: ET.Element) -> dict:
    """Extract derived column definitions from a DerivedColumn component.

    Parses output columns and input columns to identify new derived columns
    and overwrites (usageType="readWrite" on input columns).

    Args:
        component_element: An XML <component> element with
            componentClassID="Microsoft.DerivedColumn".

    Returns:
        Dictionary with key "derived_columns" containing list of derived
        column definitions.
    """
    derived_columns = []

    # Extract new derived columns from output columns
    outputs_container = component_element.find("outputs")
    if outputs_container is not None:
        for output_element in outputs_container.findall("output"):
            if output_element.get("isErrorOut", "").lower() == "true":
                continue

            output_columns_container = output_element.find("outputColumns")
            if output_columns_container is None:
                continue

            for col in output_columns_container.findall("outputColumn"):
                col_def = _extract_derived_column_definition(col)
                if col_def is not None:
                    derived_columns.append(col_def)

    # Extract overwrites from input columns with usageType="readWrite"
    inputs_container = component_element.find("inputs")
    if inputs_container is not None:
        for input_element in inputs_container.findall("input"):
            input_columns_container = input_element.find("inputColumns")
            if input_columns_container is None:
                continue

            for col in input_columns_container.findall("inputColumn"):
                usage_type = col.get("usageType", "")
                if usage_type == "readWrite":
                    overwrite_def = _extract_overwrite_definition(col)
                    if overwrite_def is not None:
                        derived_columns.append(overwrite_def)

    return {"derived_columns": derived_columns}


def _extract_derived_column_definition(col_element: ET.Element) -> dict | None:
    """Extract a single new derived column definition from an outputColumn.

    Args:
        col_element: An <outputColumn> XML element.

    Returns:
        Dictionary with column definition or None if no Expression property found.
    """
    properties_container = col_element.find("properties")
    if properties_container is None:
        return None

    expression = ""
    friendly_expression = ""

    for prop in properties_container.findall("property"):
        prop_name = prop.get("name", "")
        if prop_name == "Expression":
            expression = prop.text or ""
        elif prop_name == "FriendlyExpression":
            friendly_expression = prop.text or ""

    if not expression:
        return None

    return {
        "column_name": col_element.get("name", ""),
        "expression": expression,
        "friendly_expression": friendly_expression,
        "data_type": col_element.get("dataType", ""),
        "length": col_element.get("length", ""),
        "precision": col_element.get("precision", ""),
        "scale": col_element.get("scale", ""),
        "code_page": col_element.get("codePage", ""),
        "is_overwrite": False,
    }


def _extract_overwrite_definition(col_element: ET.Element) -> dict | None:
    """Extract a derived column overwrite definition from an inputColumn.

    An overwrite is identified by usageType="readWrite" on the input column.
    The expression and friendly expression are in the column's properties.

    Raises ValueError if required elements (lineageId, Expression) are missing,
    per Requirement 10.7.

    Args:
        col_element: An <inputColumn> XML element with usageType="readWrite".

    Returns:
        Dictionary with overwrite column definition.

    Raises:
        ValueError: If required elements for overwrite extraction are missing.
    """
    lineage_id = col_element.get("lineageId", "")
    cached_name = col_element.get("cachedName", "")

    if not lineage_id:
        raise ValueError(
            f"Missing lineageId on readWrite inputColumn '{cached_name}' "
            "required for derived column overwrite extraction"
        )

    properties_container = col_element.find("properties")
    if properties_container is None:
        raise ValueError(
            f"Missing properties on readWrite inputColumn '{cached_name}' "
            "required for derived column overwrite extraction"
        )

    expression = ""
    friendly_expression = ""

    for prop in properties_container.findall("property"):
        prop_name = prop.get("name", "")
        if prop_name == "Expression":
            expression = prop.text or ""
        elif prop_name == "FriendlyExpression":
            friendly_expression = prop.text or ""

    if not expression:
        raise ValueError(
            f"Missing Expression property on readWrite inputColumn '{cached_name}' "
            "required for derived column overwrite extraction"
        )

    return {
        "column_name": cached_name,
        "expression": expression,
        "friendly_expression": friendly_expression,
        "original_lineage_id": lineage_id,
        "is_overwrite": True,
    }


def extract_merge_join(component_element: ET.Element) -> dict:
    """Extract merge join-specific configuration from a component element.

    Parses the JoinType property (translating 0→FULL, 1→LEFT, 2→INNER),
    the TreatNullsAsEqual property, join key column pairs from input columns
    with non-zero cachedSortKeyPosition, and the output column selection.

    Args:
        component_element: An XML <component> element with
            componentClassID="Microsoft.MergeJoin".

    Returns:
        Dictionary with keys: join_type, treat_nulls_as_equal, join_keys,
        output_columns.
    """
    join_type = _extract_join_type(component_element)
    treat_nulls_as_equal = _extract_treat_nulls_as_equal(component_element)
    join_keys = _extract_join_keys(component_element)
    output_columns = _extract_merge_join_output_columns(component_element)

    return {
        "join_type": join_type,
        "treat_nulls_as_equal": treat_nulls_as_equal,
        "join_keys": join_keys,
        "output_columns": output_columns,
    }


def _extract_join_type(component_element: ET.Element) -> str:
    """Extract and translate the JoinType property.

    Looks up the numeric JoinType value in the JOIN_TYPE_MAP.
    Returns "UNKNOWN" if the value is not recognized or missing.

    Args:
        component_element: An XML <component> element.

    Returns:
        Human-readable join type string (FULL, LEFT, INNER, or UNKNOWN).
    """
    properties_container = component_element.find("properties")
    if properties_container is None:
        return "UNKNOWN"

    for prop in properties_container.findall("property"):
        if prop.get("name") == "JoinType":
            raw_value = (prop.text or "").strip()
            return JOIN_TYPE_MAP.get(raw_value, "UNKNOWN")

    return "UNKNOWN"


def _extract_treat_nulls_as_equal(component_element: ET.Element) -> bool:
    """Extract the TreatNullsAsEqual property value.

    Returns False if the property is missing or has any value other than
    "true" or "1".

    Args:
        component_element: An XML <component> element.

    Returns:
        Boolean indicating whether nulls are treated as equal.
    """
    properties_container = component_element.find("properties")
    if properties_container is None:
        return False

    for prop in properties_container.findall("property"):
        if prop.get("name") == "TreatNullsAsEqual":
            raw_value = (prop.text or "").strip().lower()
            return raw_value in ("true", "1")

    return False


def _extract_join_keys(component_element: ET.Element) -> list[dict]:
    """Extract join key pairs from input columns with cachedSortKeyPosition.

    Join keys are identified by input columns that have a non-zero
    cachedSortKeyPosition attribute. The first input (index 0) is the left
    input, and the second input (index 1) is the right input. Key pairs
    are matched by their absolute cachedSortKeyPosition values.

    Args:
        component_element: An XML <component> element.

    Returns:
        List of dicts, each with keys: left_column, right_column,
        sort_key_position.
    """
    inputs_container = component_element.find("inputs")
    if inputs_container is None:
        return []

    input_elements = inputs_container.findall("input")
    if len(input_elements) < 2:
        return []

    left_input = input_elements[0]
    right_input = input_elements[1]

    left_keys = _get_key_columns(left_input)
    right_keys = _get_key_columns(right_input)

    # Match key pairs by their absolute sort key position
    join_keys = []
    all_positions = sorted(set(left_keys.keys()) | set(right_keys.keys()))
    for position in all_positions:
        left_col = left_keys.get(position, "")
        right_col = right_keys.get(position, "")
        join_keys.append(
            {
                "left_column": left_col,
                "right_column": right_col,
                "sort_key_position": position,
            }
        )

    return join_keys


def _get_key_columns(input_element: ET.Element) -> dict[int, str]:
    """Get key columns from an input element.

    Extracts columns with non-zero cachedSortKeyPosition and returns a
    mapping from absolute sort key position to column name (cachedName).

    Args:
        input_element: An XML <input> element.

    Returns:
        Dict mapping absolute sort key position (int) to column name (str).
    """
    key_columns: dict[int, str] = {}

    input_columns_container = input_element.find("inputColumns")
    if input_columns_container is None:
        return key_columns

    for col in input_columns_container.findall("inputColumn"):
        sort_key_pos_str = col.get("cachedSortKeyPosition", "")
        if not sort_key_pos_str:
            continue

        try:
            sort_key_pos = int(sort_key_pos_str)
        except ValueError:
            continue

        if sort_key_pos == 0:
            continue

        abs_position = abs(sort_key_pos)
        cached_name = col.get("cachedName", "")
        key_columns[abs_position] = cached_name

    return key_columns


def _extract_merge_join_output_columns(component_element: ET.Element) -> list[dict]:
    """Extract output columns from the merge join's non-error output.

    Looks for the first output that is not an error output and extracts
    each outputColumn with its name, dataType, length, precision, scale,
    codePage, and lineageId.

    Args:
        component_element: An XML <component> element.

    Returns:
        List of dicts, each representing an output column with keys:
        name, data_type, length, precision, scale, code_page, lineage_id.
    """
    outputs_container = component_element.find("outputs")
    if outputs_container is None:
        return []

    for output_element in outputs_container.findall("output"):
        # Skip error outputs
        is_error_out = output_element.get("isErrorOut", "").lower() == "true"
        if is_error_out:
            continue

        output_columns_container = output_element.find("outputColumns")
        if output_columns_container is None:
            return []

        columns = []
        for col in output_columns_container.findall("outputColumn"):
            columns.append(
                {
                    "name": col.get("name", ""),
                    "data_type": col.get("dataType", ""),
                    "length": col.get("length", ""),
                    "precision": col.get("precision", ""),
                    "scale": col.get("scale", ""),
                    "code_page": col.get("codePage", ""),
                    "lineage_id": col.get("lineageId", ""),
                }
            )

        return columns

    return []
