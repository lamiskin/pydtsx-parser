"""Tests for pydtsx_parser.xml_utils module."""

import pytest

from pydtsx_parser.errors import FileNotFoundError, MalformedXMLError
from pydtsx_parser.xml_utils import (
    count_elements_and_attributes,
    get_all_attributes,
    parse_xml,
    strip_namespace,
)

# --- Fixtures ---


@pytest.fixture
def valid_xml_file(tmp_path):
    """Create a minimal valid XML file."""
    content = '<?xml version="1.0"?>\n<root attr1="val1"><child attr2="val2"/></root>'
    path = tmp_path / "valid.xml"
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def ssis_xml_file(tmp_path):
    """Create an XML file with SSIS-like namespaces."""
    content = (
        '<?xml version="1.0"?>\n'
        '<DTS:Executable xmlns:DTS="www.microsoft.com/SqlServer/Dts" '
        'DTS:refId="Package" DTS:ObjectName="MyPackage">\n'
        '  <DTS:Variable DTS:ObjectName="Var1" DTS:Namespace="User" />\n'
        "</DTS:Executable>"
    )
    path = tmp_path / "package.dtsx"
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def xml_with_comments(tmp_path):
    """Create an XML file with comments and processing instructions."""
    content = (
        '<?xml version="1.0"?>\n'
        "<!-- This is a comment -->\n"
        "<root>\n"
        "  <!-- Another comment -->\n"
        '  <child attr="val"/>\n'
        "</root>"
    )
    path = tmp_path / "commented.xml"
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def malformed_xml_file(tmp_path):
    """Create a malformed XML file."""
    content = "<root><unclosed>"
    path = tmp_path / "malformed.xml"
    path.write_text(content, encoding="utf-8")
    return str(path)


# --- parse_xml tests ---


class TestParseXml:
    def test_parse_valid_xml(self, valid_xml_file):
        tree = parse_xml(valid_xml_file)
        assert tree is not None
        root = tree.getroot()
        assert root.tag == "root"

    def test_parse_ssis_xml(self, ssis_xml_file):
        tree = parse_xml(ssis_xml_file)
        root = tree.getroot()
        assert "Executable" in root.tag

    def test_file_not_found_raises_custom_error(self):
        with pytest.raises(FileNotFoundError) as exc_info:
            parse_xml("/nonexistent/path/file.dtsx")
        assert "File not found" in exc_info.value.reason

    def test_empty_path_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_xml("")

    def test_none_path_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_xml(None)

    def test_malformed_xml_raises_error(self, malformed_xml_file):
        with pytest.raises(MalformedXMLError) as exc_info:
            parse_xml(malformed_xml_file)
        assert malformed_xml_file in exc_info.value.file_path
        assert "Malformed XML" in exc_info.value.reason

    def test_file_not_found_priority_over_malformed(self):
        """File not found takes priority even if path looks like it could be malformed."""
        with pytest.raises(FileNotFoundError):
            parse_xml("/nonexistent/malformed.xml")

    def test_directory_path_raises_file_not_found(self, tmp_path):
        """A directory path is not a valid file."""
        with pytest.raises(FileNotFoundError):
            parse_xml(str(tmp_path))


# --- get_all_attributes tests ---


class TestGetAllAttributes:
    def test_simple_attributes(self, valid_xml_file):
        tree = parse_xml(valid_xml_file)
        root = tree.getroot()
        attrs = get_all_attributes(root)
        assert attrs == {"attr1": "val1"}

    def test_namespace_prefixed_attributes(self, ssis_xml_file):
        tree = parse_xml(ssis_xml_file)
        root = tree.getroot()
        attrs = get_all_attributes(root)
        assert "DTS:refId" in attrs
        assert attrs["DTS:refId"] == "Package"
        assert "DTS:ObjectName" in attrs
        assert attrs["DTS:ObjectName"] == "MyPackage"

    def test_child_element_attributes(self, ssis_xml_file):
        tree = parse_xml(ssis_xml_file)
        root = tree.getroot()
        variable = root.find(".//{www.microsoft.com/SqlServer/Dts}Variable")
        attrs = get_all_attributes(variable)
        assert "DTS:ObjectName" in attrs
        assert attrs["DTS:ObjectName"] == "Var1"
        assert "DTS:Namespace" in attrs
        assert attrs["DTS:Namespace"] == "User"

    def test_element_with_no_attributes(self):
        import xml.etree.ElementTree as ET

        elem = ET.Element("empty")
        attrs = get_all_attributes(elem)
        assert attrs == {}

    def test_mixed_namespace_and_plain_attributes(self):
        import xml.etree.ElementTree as ET

        elem = ET.Element("test")
        elem.set("{www.microsoft.com/SqlServer/Dts}ObjectName", "MyObj")
        elem.set("plain", "value")
        attrs = get_all_attributes(elem)
        assert "DTS:ObjectName" in attrs
        assert "plain" in attrs
        assert attrs["DTS:ObjectName"] == "MyObj"
        assert attrs["plain"] == "value"

    def test_unknown_namespace_kept_as_is(self):
        import xml.etree.ElementTree as ET

        elem = ET.Element("test")
        elem.set("{http://unknown.ns/foo}Bar", "baz")
        attrs = get_all_attributes(elem)
        # Unknown namespaces keep the {uri}Name format
        assert "{http://unknown.ns/foo}Bar" in attrs
        assert attrs["{http://unknown.ns/foo}Bar"] == "baz"


# --- count_elements_and_attributes tests ---


class TestCountElementsAndAttributes:
    def test_simple_xml(self, valid_xml_file):
        tree = parse_xml(valid_xml_file)
        elements, attributes, skipped = count_elements_and_attributes(tree)
        # root (1 attr) + child (1 attr) = 2 elements, 2 attributes
        assert elements == 2
        assert attributes == 2
        assert skipped == []

    def test_ssis_xml(self, ssis_xml_file):
        tree = parse_xml(ssis_xml_file)
        elements, attributes, skipped = count_elements_and_attributes(tree)
        # DTS:Executable (2 attrs) + DTS:Variable (2 attrs) = 2 elements, 4 attributes
        assert elements == 2
        assert attributes == 4
        assert skipped == []

    def test_xml_with_comments(self, xml_with_comments):
        tree = parse_xml(xml_with_comments)
        elements, attributes, skipped = count_elements_and_attributes(tree)
        # root (0 attrs) + child (1 attr) = 2 elements, 1 attribute
        assert elements == 2
        assert attributes == 1
        # Only the comment inside the root element is captured
        # (the one before <root> is outside the tree)
        assert len(skipped) >= 1
        assert any("Another comment" in item for item in skipped)

    def test_empty_root_only(self, tmp_path):
        content = '<?xml version="1.0"?>\n<root/>'
        path = tmp_path / "empty.xml"
        path.write_text(content, encoding="utf-8")
        tree = parse_xml(str(path))
        elements, attributes, skipped = count_elements_and_attributes(tree)
        assert elements == 1
        assert attributes == 0
        assert skipped == []


# --- strip_namespace tests ---


class TestStripNamespace:
    def test_strip_dts_namespace(self):
        tag = "{www.microsoft.com/SqlServer/Dts}Executable"
        assert strip_namespace(tag) == "Executable"

    def test_strip_ssis_namespace(self):
        tag = "{www.microsoft.com/SqlServer/SSIS}Parameters"
        assert strip_namespace(tag) == "Parameters"

    def test_strip_sqltask_namespace(self):
        tag = "{www.microsoft.com/sqlserver/dts/tasks/sqltask}SqlTaskData"
        assert strip_namespace(tag) == "SqlTaskData"

    def test_no_namespace(self):
        tag = "PlainElement"
        assert strip_namespace(tag) == "PlainElement"

    def test_empty_string(self):
        assert strip_namespace("") == ""

    def test_arbitrary_namespace(self):
        tag = "{http://some.other.namespace}Element"
        assert strip_namespace(tag) == "Element"
