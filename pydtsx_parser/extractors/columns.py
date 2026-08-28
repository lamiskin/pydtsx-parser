"""Column metadata and lineage extraction from SSIS data flow XML.

Extracts input columns, output columns, and external metadata columns from
data flow component input/output elements. These elements are in the default
namespace (no prefix) unlike the DTS-namespaced package-level elements.

Input columns carry cached metadata from upstream components and a lineageId
that traces back to the original output column. Output columns define the
data shape produced by a component. External metadata columns represent the
external source/destination schema (e.g., database table columns).
"""

import xml.etree.ElementTree as ET


def extract_input_columns(input_element: ET.Element) -> list[dict]:
    """Extract inputColumn elements with lineageId and cached metadata.

    Looks for an <inputColumns> child element within the given input element,
    then extracts each <inputColumn> with its attributes.

    Args:
        input_element: An XML <input> element from a data flow component.

    Returns:
        List of dicts, each representing an input column with keys:
        ref_id, cached_name, cached_data_type, cached_length,
        cached_precision, cached_scale, cached_codepage, lineage_id,
        external_metadata_column_id.
    """
    columns_container = input_element.find("inputColumns")
    if columns_container is None:
        return []

    results = []
    for col_element in columns_container.findall("inputColumn"):
        column = _extract_single_input_column(col_element)
        results.append(column)

    return results


def extract_output_columns(output_element: ET.Element) -> list[dict]:
    """Extract outputColumn elements with dataType, lineageId, and dispositions.

    Looks for an <outputColumns> child element within the given output element,
    then extracts each <outputColumn> with its attributes.

    Args:
        output_element: An XML <output> element from a data flow component.

    Returns:
        List of dicts, each representing an output column with keys:
        ref_id, name, data_type, length, precision, scale, code_page,
        lineage_id, error_row_disposition, truncation_row_disposition.
    """
    columns_container = output_element.find("outputColumns")
    if columns_container is None:
        return []

    results = []
    for col_element in columns_container.findall("outputColumn"):
        column = _extract_single_output_column(col_element)
        results.append(column)

    return results


def extract_external_metadata(metadata_element: ET.Element) -> list[dict]:
    """Extract externalMetadataColumn elements from an input or output.

    Looks for an <externalMetadataColumns> child element, then extracts
    each <externalMetadataColumn> with its schema metadata.

    Args:
        metadata_element: An XML <input> or <output> element that may contain
            an <externalMetadataColumns> child.

    Returns:
        List of dicts, each representing an external metadata column with keys:
        ref_id, name, data_type, length, precision, scale, code_page.
    """
    columns_container = metadata_element.find("externalMetadataColumns")
    if columns_container is None:
        return []

    results = []
    for col_element in columns_container.findall("externalMetadataColumn"):
        column = _extract_single_external_metadata_column(col_element)
        results.append(column)

    return results


def _extract_single_input_column(col_element: ET.Element) -> dict:
    """Extract a single inputColumn element into a dictionary.

    Args:
        col_element: An <inputColumn> XML element.

    Returns:
        Dictionary with input column metadata.
    """
    return {
        "ref_id": col_element.get("refId", ""),
        "cached_name": col_element.get("cachedName", ""),
        "cached_data_type": col_element.get("cachedDataType", ""),
        "cached_length": col_element.get("cachedLength", ""),
        "cached_precision": col_element.get("cachedPrecision", ""),
        "cached_scale": col_element.get("cachedScale", ""),
        "cached_codepage": col_element.get("cachedCodepage", ""),
        "lineage_id": col_element.get("lineageId", ""),
        "external_metadata_column_id": col_element.get("externalMetadataColumnId", ""),
    }


def _extract_single_output_column(col_element: ET.Element) -> dict:
    """Extract a single outputColumn element into a dictionary.

    Args:
        col_element: An <outputColumn> XML element.

    Returns:
        Dictionary with output column metadata.
    """
    return {
        "ref_id": col_element.get("refId", ""),
        "name": col_element.get("name", ""),
        "data_type": col_element.get("dataType", ""),
        "length": col_element.get("length", ""),
        "precision": col_element.get("precision", ""),
        "scale": col_element.get("scale", ""),
        "code_page": col_element.get("codePage", ""),
        "lineage_id": col_element.get("lineageId", ""),
        "error_row_disposition": col_element.get("errorRowDisposition", ""),
        "truncation_row_disposition": col_element.get("truncationRowDisposition", ""),
    }


def _extract_single_external_metadata_column(col_element: ET.Element) -> dict:
    """Extract a single externalMetadataColumn element into a dictionary.

    Args:
        col_element: An <externalMetadataColumn> XML element.

    Returns:
        Dictionary with external metadata column schema.
    """
    return {
        "ref_id": col_element.get("refId", ""),
        "name": col_element.get("name", ""),
        "data_type": col_element.get("dataType", ""),
        "length": col_element.get("length", ""),
        "precision": col_element.get("precision", ""),
        "scale": col_element.get("scale", ""),
        "code_page": col_element.get("codePage", ""),
    }
