"""Property-based tests for DTSX package parsing.

Uses Hypothesis to verify correctness properties of the DTSX parser:
- Property 1: No Data Loss (Element/Attribute Count Match)
- Property 16: Malformed XML Produces Descriptive Error
- Property 17: Optional Attribute Omission

**Validates: Requirements 1.6, 1.8, 7.1, 7.2, 7.3, 7.5**
"""

import os
import tempfile
import xml.etree.ElementTree as ET

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pydtsx_parser.errors import MalformedXMLError
from pydtsx_parser.parsers.dtsx import parse_dtsx

# DTS namespace used in SSIS files
DTS_NS = "www.microsoft.com/SqlServer/Dts"

# All optional package-level attributes from _PACKAGE_ATTRIBUTE_MAP
_ALL_OPTIONAL_ATTRIBUTES = [
    "refId",
    "CreationDate",
    "CreationName",
    "CreatorComputerName",
    "CreatorName",
    "DTSID",
    "ExecutableType",
    "LastModifiedProductVersion",
    "LocaleID",
    "ObjectName",
    "PackageType",
    "VersionBuild",
    "VersionGUID",
]

# Corresponding snake_case output keys for each attribute
_ATTRIBUTE_TO_KEY = {
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


# --- Strategies ---

# Strategy for generating safe attribute values (no XML-breaking chars)
safe_attr_value = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters="_-. {}",
    ),
    min_size=1,
    max_size=50,
)

# Strategy for generating random subsets of optional attributes
optional_attr_subset = st.lists(
    st.sampled_from(_ALL_OPTIONAL_ATTRIBUTES),
    min_size=0,
    max_size=len(_ALL_OPTIONAL_ATTRIBUTES),
    unique=True,
)

# Strategy for number of properties to include
num_properties = st.integers(min_value=0, max_value=5)

# Strategy for number of variables
num_variables = st.integers(min_value=0, max_value=3)

# Strategy for number of child executables
num_executables = st.integers(min_value=0, max_value=2)

# Strategy for property names
property_name = st.sampled_from(
    [
        "PackageFormatVersion",
        "ProtectionLevel",
        "VersionComments",
        "FailParentOnFailure",
        "MaximumErrorCount",
    ]
)

# Strategy for property values
property_value = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"), whitelist_characters=" _-."
    ),
    min_size=1,
    max_size=20,
)

# Strategy for variable data types
variable_data_type = st.sampled_from(["2", "3", "4", "5", "8", "11", "20"])

# Strategy for variable values
variable_value = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"), whitelist_characters=" _-."
    ),
    min_size=0,
    max_size=30,
)

# Strategy for whether to include an XML comment
include_comment = st.booleans()


# --- Helpers ---


def _build_dtsx_xml(
    attrs_to_include: list[str],
    attr_values: dict[str, str],
    properties: list[tuple[str, str]],
    variables: list[tuple[str, str, str]],
    num_execs: int,
    add_comment: bool,
) -> str:
    """Build a valid DTSX XML string with given parameters.

    Args:
        attrs_to_include: List of DTS attribute names to include on root element.
        attr_values: Map of attribute name -> value for included attributes.
        properties: List of (name, value) tuples for DTS:Property elements.
        variables: List of (name, namespace, value) tuples for variables.
        num_execs: Number of child executables to include.
        add_comment: Whether to add an XML comment.

    Returns:
        A valid DTSX XML string.
    """
    # Build root attributes
    attr_parts = [f'xmlns:DTS="{DTS_NS}"']
    for attr_name in attrs_to_include:
        value = attr_values.get(attr_name, f"val_{attr_name}")
        # Escape XML special chars in attribute values
        value = value.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
        attr_parts.append(f'DTS:{attr_name}="{value}"')

    attrs_str = " ".join(attr_parts)

    # Build child elements
    children = []

    if add_comment:
        children.append("  <!-- Generated test comment -->")

    for prop_name, prop_val in properties:
        prop_val_escaped = prop_val.replace("&", "&amp;").replace("<", "&lt;")
        children.append(
            f'  <DTS:Property DTS:Name="{prop_name}">{prop_val_escaped}</DTS:Property>'
        )

    if variables:
        var_elems = []
        for var_name, var_ns, var_val in variables:
            var_val_escaped = var_val.replace("&", "&amp;").replace("<", "&lt;")
            var_elems.append(
                f'    <DTS:Variable DTS:ObjectName="{var_name}" DTS:Namespace="{var_ns}">\n'
                f'      <DTS:VariableValue DTS:DataType="8">{var_val_escaped}</DTS:VariableValue>\n'
                f"    </DTS:Variable>"
            )
        children.append("  <DTS:Variables>")
        children.extend(var_elems)
        children.append("  </DTS:Variables>")

    if num_execs > 0:
        exec_elems = []
        for i in range(num_execs):
            exec_elems.append(
                f"    <DTS:Executable\n"
                f'      DTS:refId="Package\\\\Task{i}"\n'
                f'      DTS:CreationName="Microsoft.Pipeline"\n'
                f'      DTS:DTSID="{{{{TASK-{i}}}}}"\n'
                f'      DTS:ObjectName="Task{i}">\n'
                f"      <DTS:Variables />\n"
                f"    </DTS:Executable>"
            )
        children.append("  <DTS:Executables>")
        children.extend(exec_elems)
        children.append("  </DTS:Executables>")

    children_str = "\n".join(children)

    xml = f'<?xml version="1.0"?>\n<DTS:Executable {attrs_str}>\n{children_str}\n</DTS:Executable>'
    return xml


def _write_temp_dtsx(xml_content: str) -> str:
    """Write XML content to a temporary .dtsx file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".dtsx")
    try:
        os.write(fd, xml_content.encode("utf-8"))
    finally:
        os.close(fd)
    return path


def _count_elements_and_attributes_independently(file_path: str) -> tuple[int, int]:
    """Independently count elements and attributes in an XML file.

    Uses the same TreeBuilder configuration as the parser (insert_comments=True,
    insert_pis=True) to ensure the same tree structure, but counts independently.

    Returns:
        (total_elements, total_attributes) excluding comments and PIs.
    """
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    tree = ET.parse(file_path, parser=parser)
    root = tree.getroot()

    total_elements = 0
    total_attributes = 0

    for element in root.iter():
        # Skip comments and processing instructions
        if element.tag is ET.Comment:
            continue
        if element.tag is ET.ProcessingInstruction:
            continue
        total_elements += 1
        total_attributes += len(element.attrib)

    return total_elements, total_attributes


# --- Property 1: No Data Loss (Element/Attribute Count Match) ---
# Feature: pydtsx-parser, Property 1: No Data Loss (Element/Attribute Count Match)


class TestPropertyNoDataLoss:
    """Property 1: No Data Loss (Element/Attribute Count Match).

    For any valid SSIS XML file, the total_elements and total_attributes counts
    in the parser's completeness_summary output SHALL equal the counts obtained
    by independently traversing the source XML and counting all elements and all
    attributes.

    **Validates: Requirements 7.1, 7.2, 7.3, 7.5**
    """

    @given(
        attrs_subset=optional_attr_subset,
        attr_values=st.dictionaries(
            st.sampled_from(_ALL_OPTIONAL_ATTRIBUTES),
            safe_attr_value,
            min_size=0,
            max_size=len(_ALL_OPTIONAL_ATTRIBUTES),
        ),
        num_props=num_properties,
        prop_names=st.lists(property_name, min_size=0, max_size=5),
        prop_values=st.lists(property_value, min_size=0, max_size=5),
        num_vars=num_variables,
        var_names=st.lists(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("L",), whitelist_characters="_"
                ),
                min_size=1,
                max_size=15,
            ),
            min_size=0,
            max_size=3,
        ),
        var_values=st.lists(variable_value, min_size=0, max_size=3),
        num_execs=num_executables,
        add_comment=include_comment,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_element_attribute_counts_match_independent_traversal(
        self,
        attrs_subset,
        attr_values,
        num_props,
        prop_names,
        prop_values,
        num_vars,
        var_names,
        var_values,
        num_execs,
        add_comment,
    ):
        """Parser completeness_summary counts match independent XML traversal."""
        # Feature: pydtsx-parser, Property 1: No Data Loss (Element/Attribute Count Match)

        # Build properties list from generated data
        actual_num_props = min(num_props, len(prop_names), len(prop_values))
        properties = list(
            zip(prop_names[:actual_num_props], prop_values[:actual_num_props])
        )

        # Build variables list
        actual_num_vars = min(num_vars, len(var_names), len(var_values))
        variables = [
            (var_names[i], "User", var_values[i]) for i in range(actual_num_vars)
        ]

        # Generate the XML
        xml = _build_dtsx_xml(
            attrs_to_include=attrs_subset,
            attr_values=attr_values,
            properties=properties,
            variables=variables,
            num_execs=num_execs,
            add_comment=add_comment,
        )

        path = _write_temp_dtsx(xml)
        try:
            # Parse with our parser
            result = parse_dtsx(path)
            summary = result["completeness_summary"]

            # Independently count elements and attributes
            expected_elements, expected_attributes = (
                _count_elements_and_attributes_independently(path)
            )

            assert summary["total_elements"] == expected_elements, (
                f"Element count mismatch: parser={summary['total_elements']}, "
                f"independent={expected_elements}"
            )
            assert summary["total_attributes"] == expected_attributes, (
                f"Attribute count mismatch: parser={summary['total_attributes']}, "
                f"independent={expected_attributes}"
            )
        finally:
            os.unlink(path)


# --- Property 16: Malformed XML Produces Descriptive Error ---
# Feature: pydtsx-parser, Property 16: Malformed XML Produces Descriptive Error


# Strategy for generating malformed XML variants.
# Each variant is guaranteed to NOT be parseable as valid XML.
malformed_xml_strategy = st.one_of(
    # Unclosed tags (inner tag never closed)
    st.builds(
        lambda tag: f"<{tag}><unclosed>text",
        st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=1,
            max_size=10,
        ),
    ),
    # Mismatched closing tag
    st.builds(
        lambda tag: f"<{tag}>content</{tag}x>",
        st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=1,
            max_size=10,
        ),
    ),
    # Broken entity references (unresolvable entity)
    st.just('<root attr="value&broken">text</root>'),
    # Extra content after root close
    st.builds(
        lambda tag: f"<{tag}>ok</{tag}><extra/>",
        st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=1,
            max_size=10,
        ),
    ),
    # Completely empty (no XML at all)
    st.just(""),
    # Only whitespace (not valid XML)
    st.just("   \n  "),
    # Just text, no root element
    st.just("this is not xml at all"),
    # Unclosed root tag with attributes
    st.builds(
        lambda tag: f'<{tag} attr="value">content',
        st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=1,
            max_size=10,
        ),
    ),
    # Invalid attribute syntax (no quotes)
    st.just("<root attr=noquotes>text</root>"),
    # Duplicate root elements (not well-formed)
    st.just("<a/><b/>"),
)


class TestPropertyMalformedXmlDescriptiveError:
    """Property 16: Malformed XML Produces Descriptive Error.

    For any file containing malformed XML, the parser SHALL return an error
    containing both the file path and the XML parser exception details.

    **Validates: Requirements 1.6**
    """

    @given(malformed_content=malformed_xml_strategy)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_malformed_xml_raises_error_with_path_and_details(self, malformed_content):
        """Malformed XML always raises MalformedXMLError with file_path and reason."""
        # Feature: pydtsx-parser, Property 16: Malformed XML Produces Descriptive Error

        path = _write_temp_dtsx(malformed_content)
        try:
            with pytest.raises(MalformedXMLError) as exc_info:
                parse_dtsx(path)

            error = exc_info.value
            # Error must contain the file path
            assert error.file_path == path, (
                f"Error file_path should be '{path}', got '{error.file_path}'"
            )
            # Error must contain a descriptive reason
            assert error.reason is not None and len(error.reason) > 0, (
                "Error reason should be non-empty"
            )
            # Reason should mention it's a malformed XML issue
            assert "Malformed XML" in error.reason or "XML" in error.reason, (
                f"Error reason should reference XML parsing: '{error.reason}'"
            )
        finally:
            os.unlink(path)


# --- Property 17: Optional Attribute Omission ---
# Feature: pydtsx-parser, Property 17: Optional Attribute Omission


class TestPropertyOptionalAttributeOmission:
    """Property 17: Optional Attribute Omission.

    For any package-level attribute not present in the source .dtsx file, the
    parser's output SHALL NOT contain a key for that attribute (it shall be
    omitted rather than included with null or empty value).

    **Validates: Requirements 1.8**
    """

    @given(
        attrs_subset=st.lists(
            st.sampled_from(_ALL_OPTIONAL_ATTRIBUTES),
            min_size=0,
            max_size=len(_ALL_OPTIONAL_ATTRIBUTES),
            unique=True,
        ),
        attr_values=st.dictionaries(
            st.sampled_from(_ALL_OPTIONAL_ATTRIBUTES),
            safe_attr_value,
            min_size=0,
            max_size=len(_ALL_OPTIONAL_ATTRIBUTES),
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_absent_attributes_have_no_key_in_output(self, attrs_subset, attr_values):
        """Attributes not in source XML produce no key in package_attributes output."""
        # Feature: pydtsx-parser, Property 17: Optional Attribute Omission

        # Build XML with only the selected subset of attributes
        xml = _build_dtsx_xml(
            attrs_to_include=attrs_subset,
            attr_values=attr_values,
            properties=[],
            variables=[],
            num_execs=0,
            add_comment=False,
        )

        path = _write_temp_dtsx(xml)
        try:
            result = parse_dtsx(path)
            package_attrs = result["package_attributes"]

            # Determine which attributes were NOT included
            absent_attrs = set(_ALL_OPTIONAL_ATTRIBUTES) - set(attrs_subset)

            for attr_name in absent_attrs:
                output_key = _ATTRIBUTE_TO_KEY[attr_name]
                # The key must NOT be present in the output
                assert output_key not in package_attrs, (
                    f"Attribute '{attr_name}' (key '{output_key}') was not in the "
                    f"source XML but appears in parser output"
                )

            # Also verify that present attributes DO appear (and are not null)
            for attr_name in attrs_subset:
                output_key = _ATTRIBUTE_TO_KEY[attr_name]
                assert output_key in package_attrs, (
                    f"Attribute '{attr_name}' (key '{output_key}') was in the "
                    f"source XML but missing from parser output"
                )
                assert package_attrs[output_key] is not None, (
                    f"Attribute '{output_key}' should not be None"
                )
                assert package_attrs[output_key] != "", (
                    f"Attribute '{output_key}' should not be empty string "
                    f"(should be omitted if absent, present with value if present)"
                )
        finally:
            os.unlink(path)
