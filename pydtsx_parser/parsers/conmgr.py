"""Connection manager file parser for standalone .conmgr files.

Parses standalone .conmgr XML files and produces output equivalent to
inline connection managers within a .dtsx package. Reuses the extraction
logic from pydtsx_parser.extractors.connections to ensure consistency.

A .conmgr file has the root element DTS:ConnectionManager — the same
element structure found within DTS:ConnectionManagers in a .dtsx package.
This parser simply parses the XML and delegates to the existing
extract_single_connection_manager() function.
"""

from pydtsx_parser.extractors.connections import extract_single_connection_manager
from pydtsx_parser.xml_utils import (
    count_elements_and_attributes,
    get_root,
    parse_xml,
)


def parse_conmgr(file_path: str) -> dict:
    """Parse a standalone .conmgr file and return the connection manager data.

    Produces output containing the same attributes and nested properties as
    an equivalent inline connection manager within a .dtsx package.

    The parsing pipeline:
    1. Parse XML (handles file not found / malformed XML errors)
    2. Reuse extract_single_connection_manager() on the root element
    3. Compute completeness summary

    Args:
        file_path: Path to the .conmgr file to parse.

    Returns:
        Dict with keys: connection_manager, completeness_summary.
        The connection_manager value has the same structure as entries
        returned by extract_connection_managers() for inline definitions.

    Raises:
        FileNotFoundError: If the file does not exist or path is null/empty.
        MalformedXMLError: If the file contains malformed XML.
        ExtractionError: If the connection manager is missing required attributes.
    """
    # Step 1: Parse XML (raises FileNotFoundError or MalformedXMLError)
    tree = parse_xml(file_path)
    root = get_root(tree, file_path)

    # Step 2: Extract connection manager using the shared extraction logic.
    # The root element of a .conmgr file IS the DTS:ConnectionManager element,
    # identical in structure to what appears inside DTS:ConnectionManagers in .dtsx.
    connection_manager = extract_single_connection_manager(root, file_path)

    # Step 3: Compute completeness summary
    total_elements, total_attributes, skipped_items = count_elements_and_attributes(
        tree
    )
    completeness_summary = {
        "total_elements": total_elements,
        "total_attributes": total_attributes,
        "skipped_items": skipped_items,
    }

    return {
        "connection_manager": connection_manager,
        "completeness_summary": completeness_summary,
    }
