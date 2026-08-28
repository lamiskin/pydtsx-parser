"""Unit tests for sort component extraction."""

import xml.etree.ElementTree as ET

from pydtsx_parser.extractors.components import extract_component
from pydtsx_parser.extractors.sort import (
    _extract_eliminate_duplicates,
    _extract_sort_columns,
    extract_sort_details,
)


class TestExtractSortDetails:
    """Tests for the top-level extract_sort_details function."""

    def test_basic_sort_component(self):
        """Sort component with one ascending sort column."""
        xml_str = (
            '<component refId="Package\\DFT\\Sort" name="Sort"'
            ' componentClassID="Microsoft.Sort">'
            "  <properties>"
            '    <property name="EliminateDuplicates">0</property>'
            "  </properties>"
            "  <outputs>"
            '    <output refId="Package\\DFT\\Sort.Outputs[Sort Output]"'
            '        name="Sort Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col1" name="PROJECT_ID"'
            '            dataType="131" length="0" precision="10" scale="0"'
            '            codePage="0" lineageId="42">'
            "          <properties>"
            '            <property name="SortKeyPosition">1</property>'
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_sort_details(elem)

        assert result["eliminate_duplicates"] is False
        assert len(result["sort_columns"]) == 1
        assert result["sort_columns"][0] == {
            "name": "PROJECT_ID",
            "sort_key_position": 1,
            "sort_order": "ascending",
            "comparison_flags": "0",
        }

    def test_multiple_sort_columns_with_ordering(self):
        """Multiple sort columns returned sorted by sort_key_position."""
        xml_str = (
            '<component refId="test" name="Sort"'
            ' componentClassID="Microsoft.Sort">'
            "  <properties>"
            '    <property name="EliminateDuplicates">0</property>'
            "  </properties>"
            "  <outputs>"
            '    <output refId="out" name="Sort Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col2" name="LAST_NAME"'
            '            dataType="130" length="100">'
            "          <properties>"
            '            <property name="SortKeyPosition">2</property>'
            '            <property name="ComparisonFlags">1</property>'
            "          </properties>"
            "        </outputColumn>"
            '        <outputColumn refId="col1" name="FIRST_NAME"'
            '            dataType="130" length="50">'
            "          <properties>"
            '            <property name="SortKeyPosition">1</property>'
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_sort_details(elem)

        assert len(result["sort_columns"]) == 2
        # Should be ordered by sort_key_position
        assert result["sort_columns"][0]["name"] == "FIRST_NAME"
        assert result["sort_columns"][0]["sort_key_position"] == 1
        assert result["sort_columns"][1]["name"] == "LAST_NAME"
        assert result["sort_columns"][1]["sort_key_position"] == 2

    def test_descending_sort_order(self):
        """Negative SortKeyPosition indicates descending order."""
        xml_str = (
            '<component refId="test" name="Sort"'
            ' componentClassID="Microsoft.Sort">'
            "  <properties>"
            '    <property name="EliminateDuplicates">0</property>'
            "  </properties>"
            "  <outputs>"
            '    <output refId="out" name="Sort Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col1" name="DATE_CREATED"'
            '            dataType="135">'
            "          <properties>"
            '            <property name="SortKeyPosition">-1</property>'
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_sort_details(elem)

        assert len(result["sort_columns"]) == 1
        assert result["sort_columns"][0]["sort_order"] == "descending"
        assert result["sort_columns"][0]["sort_key_position"] == 1

    def test_pass_through_columns_excluded(self):
        """Columns with SortKeyPosition=0 are pass-through and excluded."""
        xml_str = (
            '<component refId="test" name="Sort"'
            ' componentClassID="Microsoft.Sort">'
            "  <properties>"
            '    <property name="EliminateDuplicates">0</property>'
            "  </properties>"
            "  <outputs>"
            '    <output refId="out" name="Sort Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col1" name="PROJECT_ID"'
            '            dataType="131">'
            "          <properties>"
            '            <property name="SortKeyPosition">1</property>'
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            '        <outputColumn refId="col2" name="DESCRIPTION"'
            '            dataType="130">'
            "          <properties>"
            '            <property name="SortKeyPosition">0</property>'
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_sort_details(elem)

        # Only the sort key column should be present
        assert len(result["sort_columns"]) == 1
        assert result["sort_columns"][0]["name"] == "PROJECT_ID"

    def test_eliminate_duplicates_true(self):
        """EliminateDuplicates=1 sets eliminate_duplicates to True."""
        xml_str = (
            '<component refId="test" name="Sort"'
            ' componentClassID="Microsoft.Sort">'
            "  <properties>"
            '    <property name="EliminateDuplicates">1</property>'
            "  </properties>"
            "  <outputs>"
            '    <output refId="out" name="Sort Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col1" name="ID" dataType="3">'
            "          <properties>"
            '            <property name="SortKeyPosition">1</property>'
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_sort_details(elem)

        assert result["eliminate_duplicates"] is True

    def test_no_outputs_returns_empty_sort_columns(self):
        """Sort component with no outputs returns empty sort_columns."""
        xml_str = (
            '<component refId="test" name="Sort"'
            ' componentClassID="Microsoft.Sort">'
            "  <properties>"
            '    <property name="EliminateDuplicates">0</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_sort_details(elem)

        assert result["eliminate_duplicates"] is False
        assert result["sort_columns"] == []

    def test_no_properties_returns_defaults(self):
        """Sort component with no properties returns defaults."""
        xml_str = (
            '<component refId="test" name="Sort"'
            ' componentClassID="Microsoft.Sort">'
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_sort_details(elem)

        assert result["eliminate_duplicates"] is False
        assert result["sort_columns"] == []

    def test_error_output_columns_excluded(self):
        """Columns from error outputs are not included in sort_columns."""
        xml_str = (
            '<component refId="test" name="Sort"'
            ' componentClassID="Microsoft.Sort">'
            "  <properties>"
            '    <property name="EliminateDuplicates">0</property>'
            "  </properties>"
            "  <outputs>"
            '    <output refId="out1" name="Sort Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col1" name="ID" dataType="3">'
            "          <properties>"
            '            <property name="SortKeyPosition">1</property>'
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            '    <output refId="out2" name="Sort Error Output" isErrorOut="true">'
            "      <outputColumns>"
            '        <outputColumn refId="col2" name="ErrorColumn" dataType="3">'
            "          <properties>"
            '            <property name="SortKeyPosition">1</property>'
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_sort_details(elem)

        # Only the non-error output column should be included
        assert len(result["sort_columns"]) == 1
        assert result["sort_columns"][0]["name"] == "ID"

    def test_mixed_ascending_descending(self):
        """Sort with mixed ascending and descending columns."""
        xml_str = (
            '<component refId="test" name="Sort"'
            ' componentClassID="Microsoft.Sort">'
            "  <properties>"
            '    <property name="EliminateDuplicates">0</property>'
            "  </properties>"
            "  <outputs>"
            '    <output refId="out" name="Sort Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col1" name="CATEGORY"'
            '            dataType="130">'
            "          <properties>"
            '            <property name="SortKeyPosition">1</property>'
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            '        <outputColumn refId="col2" name="DATE_MODIFIED"'
            '            dataType="135">'
            "          <properties>"
            '            <property name="SortKeyPosition">-2</property>'
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_sort_details(elem)

        assert len(result["sort_columns"]) == 2
        assert result["sort_columns"][0]["sort_order"] == "ascending"
        assert result["sort_columns"][0]["sort_key_position"] == 1
        assert result["sort_columns"][1]["sort_order"] == "descending"
        assert result["sort_columns"][1]["sort_key_position"] == 2


class TestEliminateDuplicates:
    """Tests for the _extract_eliminate_duplicates helper."""

    def test_value_zero(self):
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="EliminateDuplicates">0</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_eliminate_duplicates(elem) is False

    def test_value_one(self):
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="EliminateDuplicates">1</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_eliminate_duplicates(elem) is True

    def test_missing_property(self):
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="OtherProp">abc</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_eliminate_duplicates(elem) is False

    def test_no_properties_container(self):
        xml_str = "<component></component>"
        elem = ET.fromstring(xml_str)
        assert _extract_eliminate_duplicates(elem) is False

    def test_empty_text_value(self):
        """Empty text in property treated as not eliminating duplicates."""
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="EliminateDuplicates"></property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_eliminate_duplicates(elem) is False


class TestSortColumns:
    """Tests for the _extract_sort_columns helper."""

    def test_column_without_properties_skipped(self):
        """Output columns without properties element are not sort keys."""
        xml_str = (
            "<component>"
            "  <outputs>"
            '    <output refId="out" name="Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col1" name="NoProps" dataType="3">'
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = _extract_sort_columns(elem)
        assert result == []

    def test_column_without_sort_key_position_skipped(self):
        """Output columns without SortKeyPosition property are skipped."""
        xml_str = (
            "<component>"
            "  <outputs>"
            '    <output refId="out" name="Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col1" name="NoSortKey" dataType="3">'
            "          <properties>"
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = _extract_sort_columns(elem)
        assert result == []

    def test_invalid_sort_key_position_skipped(self):
        """Non-integer SortKeyPosition values are skipped."""
        xml_str = (
            "<component>"
            "  <outputs>"
            '    <output refId="out" name="Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col1" name="BadKey" dataType="3">'
            "          <properties>"
            '            <property name="SortKeyPosition">abc</property>'
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = _extract_sort_columns(elem)
        assert result == []

    def test_comparison_flags_preserved(self):
        """ComparisonFlags value is preserved as-is."""
        xml_str = (
            "<component>"
            "  <outputs>"
            '    <output refId="out" name="Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col1" name="COL" dataType="130">'
            "          <properties>"
            '            <property name="SortKeyPosition">1</property>'
            '            <property name="ComparisonFlags">196609</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = _extract_sort_columns(elem)
        assert result[0]["comparison_flags"] == "196609"

    def test_missing_comparison_flags_defaults_to_zero(self):
        """Missing ComparisonFlags defaults to '0'."""
        xml_str = (
            "<component>"
            "  <outputs>"
            '    <output refId="out" name="Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col1" name="COL" dataType="3">'
            "          <properties>"
            '            <property name="SortKeyPosition">1</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = _extract_sort_columns(elem)
        assert result[0]["comparison_flags"] == "0"


class TestComponentIntegration:
    """Tests for sort extraction integrated with extract_component."""

    def test_sort_component_has_sort_fields(self):
        """extract_component adds sort_columns and eliminate_duplicates for Sort."""
        xml_str = (
            '<component refId="Package\\DFT\\Sort" name="Sort"'
            ' componentClassID="Microsoft.Sort"'
            ' version="1" usesDispositions="true">'
            "  <properties>"
            '    <property name="EliminateDuplicates">0</property>'
            "  </properties>"
            "  <outputs>"
            '    <output refId="Package\\DFT\\Sort.Outputs[Sort Output]"'
            '        name="Sort Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col1" name="PROJECT_ID"'
            '            dataType="131" length="0" precision="10" scale="0"'
            '            codePage="0" lineageId="42">'
            "          <properties>"
            '            <property name="SortKeyPosition">1</property>'
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["classification"] == "transformation"
        assert result["component_class_id"] == "Microsoft.Sort"
        assert result["eliminate_duplicates"] is False
        assert len(result["sort_columns"]) == 1
        assert result["sort_columns"][0] == {
            "name": "PROJECT_ID",
            "sort_key_position": 1,
            "sort_order": "ascending",
            "comparison_flags": "0",
        }

    def test_sort_component_with_no_columns(self):
        """Sort component with no configured sort columns has empty list (Req 10.6)."""
        xml_str = (
            '<component refId="Package\\DFT\\Sort" name="Sort"'
            ' componentClassID="Microsoft.Sort">'
            "  <properties>"
            '    <property name="EliminateDuplicates">0</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["classification"] == "transformation"
        assert result["eliminate_duplicates"] is False
        assert result["sort_columns"] == []

    def test_non_sort_component_no_sort_fields(self):
        """Non-sort components do not have sort_columns or eliminate_duplicates."""
        xml_str = (
            '<component refId="Package\\DFT\\Src" name="Source"'
            ' componentClassID="Microsoft.OLEDBSource">'
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert "sort_columns" not in result
        assert "eliminate_duplicates" not in result

    def test_sort_component_eliminate_duplicates_true(self):
        """Sort component with EliminateDuplicates=1."""
        xml_str = (
            '<component refId="Package\\DFT\\Sort" name="Sort Unique"'
            ' componentClassID="Microsoft.Sort">'
            "  <properties>"
            '    <property name="EliminateDuplicates">1</property>'
            "  </properties>"
            "  <outputs>"
            '    <output refId="out" name="Sort Output" isErrorOut="false">'
            "      <outputColumns>"
            '        <outputColumn refId="col1" name="ID" dataType="3">'
            "          <properties>"
            '            <property name="SortKeyPosition">-1</property>'
            '            <property name="ComparisonFlags">0</property>'
            "          </properties>"
            "        </outputColumn>"
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["eliminate_duplicates"] is True
        assert result["sort_columns"][0]["sort_order"] == "descending"
        assert result["sort_columns"][0]["sort_key_position"] == 1
