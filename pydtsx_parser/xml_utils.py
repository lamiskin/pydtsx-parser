"""XML utility functions for SSIS file parsing.

Provides namespace-aware XML parsing, attribute extraction, element/attribute
counting, and namespace stripping for DTS, SSIS, and SQLTask namespaces.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.errors import FileNotFoundError, MalformedXMLError


def parse_xml(file_path: str) -> ET.ElementTree[ET.Element[str]]:
    """Parse an XML file and return the ElementTree.

    Checks file existence first, then attempts XML parsing.
    File not found takes priority over malformed XML errors.

    Uses a TreeBuilder with insert_comments=True and insert_pis=True
    so that XML comments and processing instructions are preserved in the
    tree for completeness counting.

    Args:
        file_path: Path to the XML file to parse.

    Returns:
        The parsed ElementTree object.

    Raises:
        FileNotFoundError: If the file does not exist or is not readable.
        MalformedXMLError: If the file contains malformed XML.
    """
    if not file_path or not os.path.isfile(file_path):
        raise FileNotFoundError(file_path or "", "File not found or not readable")

    try:
        parser = ET.XMLParser(
            target=ET.TreeBuilder(insert_comments=True, insert_pis=True)
        )
        tree = ET.parse(file_path, parser=parser)
        return tree
    except ET.ParseError as e:
        raise MalformedXMLError(file_path, f"Malformed XML: {e}") from e


def get_root(
    tree: ET.ElementTree[ET.Element[str]], file_path: str = ""
) -> ET.Element[str]:
    """Return the root element of a parsed tree.

    ``ElementTree.getroot()`` is typed as optional because a tree can be
    constructed without a root element. A tree produced by :func:`parse_xml`
    always has one, and this helper makes that guarantee explicit rather than
    leaving every caller to access an ``Optional`` unguarded.

    Args:
        tree: A parsed ElementTree.
        file_path: Optional source path, used only for error reporting.

    Returns:
        The root Element.

    Raises:
        MalformedXMLError: If the tree has no root element.
    """
    root = tree.getroot()
    if root is None:
        raise MalformedXMLError(file_path, "XML document has no root element")
    return root


def get_all_attributes(element: ET.Element) -> dict:
    """Extract all attributes from an element, resolving namespace prefixes.

    Converts namespace URI prefixes like {www.microsoft.com/SqlServer/Dts}
    to human-readable prefixes like DTS: based on the NAMESPACES mapping.

    Args:
        element: An XML Element to extract attributes from.

    Returns:
        A dictionary mapping readable attribute names to their values.
        Namespace-prefixed attributes use the form "PREFIX:LocalName".
        Attributes without a known namespace prefix keep their original form.
    """
    # Build reverse lookup: URI -> prefix
    uri_to_prefix = {uri: prefix for prefix, uri in NAMESPACES.items()}

    result = {}
    for attr_name, attr_value in element.attrib.items():
        readable_name = _resolve_namespace_prefix(attr_name, uri_to_prefix)
        result[readable_name] = attr_value

    return result


def count_elements_and_attributes(
    tree: ET.ElementTree[ET.Element[str]],
) -> tuple[int, int, list[str]]:
    """Count all elements, attributes, and collect skipped items in an XML tree.

    Traverses the entire tree counting every element and every attribute.
    Also collects XML comments and processing instructions as "skipped items"
    since they are non-data constructs.

    Args:
        tree: The parsed ElementTree to analyze.

    Returns:
        A tuple of (total_elements, total_attributes, skipped_items) where:
        - total_elements: count of all XML elements in the tree
        - total_attributes: count of all XML attributes across all elements
        - skipped_items: list of comment/PI text representations
    """
    total_elements = 0
    total_attributes = 0
    skipped_items = []

    root = get_root(tree)

    # Use iter() to traverse ALL nodes including root
    for element in root.iter():
        # Comments have a callable tag (the ET.Comment function)
        if element.tag is ET.Comment:
            skipped_items.append(f"<!--{element.text}-->")
            continue

        # Processing instructions have a callable tag (the ET.ProcessingInstruction function)
        if element.tag is ET.ProcessingInstruction:
            skipped_items.append(f"<?{element.text}?>")
            continue

        # Regular elements
        total_elements += 1
        total_attributes += len(element.attrib)

    return total_elements, total_attributes, skipped_items


def strip_namespace(tag: str) -> str:
    """Remove namespace URI prefix from a tag name.

    Converts "{http://namespace.uri}LocalName" to "LocalName".
    If the tag has no namespace prefix, returns it unchanged.

    Args:
        tag: An XML tag string, potentially with a namespace URI prefix.

    Returns:
        The local name portion of the tag without any namespace URI.
    """
    if tag.startswith("{"):
        # Find the closing brace and return everything after it
        closing_brace = tag.index("}")
        return tag[closing_brace + 1 :]
    return tag


def _resolve_namespace_prefix(attr_name: str, uri_to_prefix: dict) -> str:
    """Resolve a namespace URI in an attribute name to a readable prefix.

    Args:
        attr_name: The attribute name, potentially with {uri} prefix.
        uri_to_prefix: Mapping from namespace URI to readable prefix.

    Returns:
        The attribute name with URI replaced by readable prefix,
        or the original name if no namespace or unrecognized namespace.
    """
    if not attr_name.startswith("{"):
        return attr_name

    closing_brace = attr_name.index("}")
    uri = attr_name[1:closing_brace]
    local_name = attr_name[closing_brace + 1 :]

    prefix = uri_to_prefix.get(uri)
    if prefix:
        return f"{prefix}:{local_name}"

    # Unknown namespace - keep the full URI form
    return attr_name
