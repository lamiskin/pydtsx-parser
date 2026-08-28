"""Unit tests for merge join extraction."""

import xml.etree.ElementTree as ET

from pydtsx_parser.extractors.components import extract_component
from pydtsx_parser.extractors.transformations import (
    _extract_join_keys,
    _extract_join_type,
    _extract_merge_join_output_columns,
    _extract_treat_nulls_as_equal,
    extract_merge_join,
)


class TestExtractMergeJoin:
    """Tests for the top-level extract_merge_join function."""

    def test_basic_inner_join(self):
        """Merge join with INNER join type (2) and one key pair."""
        xml_str = (
            '<component refId="Package\\DFT\\Merge Join" name="Merge Join"'
            ' componentClassID="Microsoft.MergeJoin" version="1">'
            "  <properties>"
            '    <property name="JoinType">2</property>'
            '    <property name="TreatNullsAsEqual">false</property>'
            "  </properties>"
            "  <inputs>"
            '    <input refId="left" name="Merge Join Left Input">'
            "      <inputColumns>"
            '        <inputColumn cachedName="PROJECT_ID"'
            '            cachedSortKeyPosition="1"'
            '            lineageId="src1.Outputs[Out].Columns[PROJECT_ID]" />'
            "      </inputColumns>"
            "    </input>"
            '    <input refId="right" name="Merge Join Right Input">'
            "      <inputColumns>"
            '        <inputColumn cachedName="PROJECT_ID"'
            '            cachedSortKeyPosition="1"'
            '            lineageId="src2.Outputs[Out].Columns[PROJECT_ID]" />'
            '        <inputColumn cachedName="TITLE"'
            '            lineageId="src2.Outputs[Out].Columns[TITLE]" />'
            "      </inputColumns>"
            "    </input>"
            "  </inputs>"
            "  <outputs>"
            '    <output refId="out" name="Merge Join Output">'
            "      <outputColumns>"
            '        <outputColumn name="PROJECT_ID" dataType="131"'
            '            length="0" precision="10" scale="0"'
            '            codePage="0" lineageId="42" />'
            '        <outputColumn name="TITLE" dataType="130"'
            '            length="200" precision="0" scale="0"'
            '            codePage="1252" lineageId="43" />'
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_merge_join(elem)

        assert result["join_type"] == "INNER"
        assert result["treat_nulls_as_equal"] is False
        assert len(result["join_keys"]) == 1
        assert result["join_keys"][0] == {
            "left_column": "PROJECT_ID",
            "right_column": "PROJECT_ID",
            "sort_key_position": 1,
        }
        assert len(result["output_columns"]) == 2
        assert result["output_columns"][0]["name"] == "PROJECT_ID"
        assert result["output_columns"][1]["name"] == "TITLE"

    def test_left_join(self):
        """JoinType=1 translates to LEFT."""
        xml_str = (
            '<component refId="test" name="MJ"'
            ' componentClassID="Microsoft.MergeJoin">'
            "  <properties>"
            '    <property name="JoinType">1</property>'
            '    <property name="TreatNullsAsEqual">true</property>'
            "  </properties>"
            "  <inputs>"
            '    <input refId="left" name="Left">'
            "      <inputColumns>"
            '        <inputColumn cachedName="ID" cachedSortKeyPosition="1"'
            '            lineageId="l1" />'
            "      </inputColumns>"
            "    </input>"
            '    <input refId="right" name="Right">'
            "      <inputColumns>"
            '        <inputColumn cachedName="ID" cachedSortKeyPosition="1"'
            '            lineageId="r1" />'
            "      </inputColumns>"
            "    </input>"
            "  </inputs>"
            "  <outputs>"
            '    <output refId="out" name="Output">'
            "      <outputColumns>"
            '        <outputColumn name="ID" dataType="3" length="0"'
            '            precision="0" scale="0" codePage="0" lineageId="50" />'
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_merge_join(elem)

        assert result["join_type"] == "LEFT"
        assert result["treat_nulls_as_equal"] is True

    def test_full_join(self):
        """JoinType=0 translates to FULL."""
        xml_str = (
            '<component refId="test" name="MJ"'
            ' componentClassID="Microsoft.MergeJoin">'
            "  <properties>"
            '    <property name="JoinType">0</property>'
            '    <property name="TreatNullsAsEqual">false</property>'
            "  </properties>"
            "  <inputs>"
            '    <input refId="left" name="Left">'
            "      <inputColumns>"
            '        <inputColumn cachedName="KEY" cachedSortKeyPosition="1"'
            '            lineageId="l1" />'
            "      </inputColumns>"
            "    </input>"
            '    <input refId="right" name="Right">'
            "      <inputColumns>"
            '        <inputColumn cachedName="KEY" cachedSortKeyPosition="1"'
            '            lineageId="r1" />'
            "      </inputColumns>"
            "    </input>"
            "  </inputs>"
            "  <outputs>"
            '    <output refId="out" name="Output">'
            "      <outputColumns />"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_merge_join(elem)

        assert result["join_type"] == "FULL"

    def test_multiple_join_keys(self):
        """Merge join with multiple key pairs matched by sort position."""
        xml_str = (
            '<component refId="test" name="MJ"'
            ' componentClassID="Microsoft.MergeJoin">'
            "  <properties>"
            '    <property name="JoinType">2</property>'
            '    <property name="TreatNullsAsEqual">false</property>'
            "  </properties>"
            "  <inputs>"
            '    <input refId="left" name="Left">'
            "      <inputColumns>"
            '        <inputColumn cachedName="DEPT_ID" cachedSortKeyPosition="2"'
            '            lineageId="l2" />'
            '        <inputColumn cachedName="ORG_ID" cachedSortKeyPosition="1"'
            '            lineageId="l1" />'
            "      </inputColumns>"
            "    </input>"
            '    <input refId="right" name="Right">'
            "      <inputColumns>"
            '        <inputColumn cachedName="DEPARTMENT" cachedSortKeyPosition="2"'
            '            lineageId="r2" />'
            '        <inputColumn cachedName="ORGANIZATION" cachedSortKeyPosition="1"'
            '            lineageId="r1" />'
            "      </inputColumns>"
            "    </input>"
            "  </inputs>"
            "  <outputs>"
            '    <output refId="out" name="Output">'
            "      <outputColumns />"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_merge_join(elem)

        assert len(result["join_keys"]) == 2
        # Should be sorted by sort_key_position
        assert result["join_keys"][0] == {
            "left_column": "ORG_ID",
            "right_column": "ORGANIZATION",
            "sort_key_position": 1,
        }
        assert result["join_keys"][1] == {
            "left_column": "DEPT_ID",
            "right_column": "DEPARTMENT",
            "sort_key_position": 2,
        }

    def test_no_inputs_returns_empty_join_keys(self):
        """Merge join with no inputs returns empty join_keys list."""
        xml_str = (
            '<component refId="test" name="MJ"'
            ' componentClassID="Microsoft.MergeJoin">'
            "  <properties>"
            '    <property name="JoinType">1</property>'
            '    <property name="TreatNullsAsEqual">false</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_merge_join(elem)

        assert result["join_type"] == "LEFT"
        assert result["join_keys"] == []
        assert result["output_columns"] == []

    def test_no_properties_returns_defaults(self):
        """Merge join with no properties returns defaults."""
        xml_str = (
            '<component refId="test" name="MJ"'
            ' componentClassID="Microsoft.MergeJoin">'
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_merge_join(elem)

        assert result["join_type"] == "UNKNOWN"
        assert result["treat_nulls_as_equal"] is False
        assert result["join_keys"] == []
        assert result["output_columns"] == []

    def test_error_output_excluded_from_output_columns(self):
        """Error output columns are not included in output_columns."""
        xml_str = (
            '<component refId="test" name="MJ"'
            ' componentClassID="Microsoft.MergeJoin">'
            "  <properties>"
            '    <property name="JoinType">2</property>'
            '    <property name="TreatNullsAsEqual">false</property>'
            "  </properties>"
            "  <inputs>"
            '    <input refId="left" name="Left">'
            "      <inputColumns>"
            '        <inputColumn cachedName="ID" cachedSortKeyPosition="1"'
            '            lineageId="l1" />'
            "      </inputColumns>"
            "    </input>"
            '    <input refId="right" name="Right">'
            "      <inputColumns>"
            '        <inputColumn cachedName="ID" cachedSortKeyPosition="1"'
            '            lineageId="r1" />'
            "      </inputColumns>"
            "    </input>"
            "  </inputs>"
            "  <outputs>"
            '    <output refId="out1" name="Merge Join Output">'
            "      <outputColumns>"
            '        <outputColumn name="ID" dataType="3" length="0"'
            '            precision="0" scale="0" codePage="0" lineageId="50" />'
            "      </outputColumns>"
            "    </output>"
            '    <output refId="out2" name="Merge Join Error Output"'
            '        isErrorOut="true">'
            "      <outputColumns>"
            '        <outputColumn name="ErrorCode" dataType="3" length="0"'
            '            precision="0" scale="0" codePage="0" lineageId="99" />'
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_merge_join(elem)

        # Only the non-error output columns should be present
        assert len(result["output_columns"]) == 1
        assert result["output_columns"][0]["name"] == "ID"

    def test_non_key_input_columns_excluded_from_join_keys(self):
        """Input columns without cachedSortKeyPosition are not join keys."""
        xml_str = (
            '<component refId="test" name="MJ"'
            ' componentClassID="Microsoft.MergeJoin">'
            "  <properties>"
            '    <property name="JoinType">2</property>'
            '    <property name="TreatNullsAsEqual">false</property>'
            "  </properties>"
            "  <inputs>"
            '    <input refId="left" name="Left">'
            "      <inputColumns>"
            '        <inputColumn cachedName="KEY_COL" cachedSortKeyPosition="1"'
            '            lineageId="l1" />'
            '        <inputColumn cachedName="VALUE_COL"'
            '            lineageId="l2" />'
            "      </inputColumns>"
            "    </input>"
            '    <input refId="right" name="Right">'
            "      <inputColumns>"
            '        <inputColumn cachedName="KEY_COL" cachedSortKeyPosition="1"'
            '            lineageId="r1" />'
            '        <inputColumn cachedName="OTHER_COL"'
            '            lineageId="r2" />'
            "      </inputColumns>"
            "    </input>"
            "  </inputs>"
            "  <outputs>"
            '    <output refId="out" name="Output">'
            "      <outputColumns />"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_merge_join(elem)

        # Only columns with cachedSortKeyPosition are join keys
        assert len(result["join_keys"]) == 1
        assert result["join_keys"][0]["left_column"] == "KEY_COL"
        assert result["join_keys"][0]["right_column"] == "KEY_COL"

    def test_zero_sort_key_position_excluded(self):
        """Columns with cachedSortKeyPosition=0 are excluded from join keys."""
        xml_str = (
            '<component refId="test" name="MJ"'
            ' componentClassID="Microsoft.MergeJoin">'
            "  <properties>"
            '    <property name="JoinType">1</property>'
            '    <property name="TreatNullsAsEqual">false</property>'
            "  </properties>"
            "  <inputs>"
            '    <input refId="left" name="Left">'
            "      <inputColumns>"
            '        <inputColumn cachedName="KEY" cachedSortKeyPosition="1"'
            '            lineageId="l1" />'
            '        <inputColumn cachedName="PASS" cachedSortKeyPosition="0"'
            '            lineageId="l2" />'
            "      </inputColumns>"
            "    </input>"
            '    <input refId="right" name="Right">'
            "      <inputColumns>"
            '        <inputColumn cachedName="KEY" cachedSortKeyPosition="1"'
            '            lineageId="r1" />'
            "      </inputColumns>"
            "    </input>"
            "  </inputs>"
            "  <outputs>"
            '    <output refId="out" name="Output">'
            "      <outputColumns />"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_merge_join(elem)

        assert len(result["join_keys"]) == 1
        assert result["join_keys"][0]["left_column"] == "KEY"


class TestJoinType:
    """Tests for the _extract_join_type helper."""

    def test_join_type_0_is_full(self):
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="JoinType">0</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_join_type(elem) == "FULL"

    def test_join_type_1_is_left(self):
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="JoinType">1</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_join_type(elem) == "LEFT"

    def test_join_type_2_is_inner(self):
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="JoinType">2</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_join_type(elem) == "INNER"

    def test_unknown_join_type(self):
        """Unrecognized numeric JoinType returns UNKNOWN."""
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="JoinType">99</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_join_type(elem) == "UNKNOWN"

    def test_missing_join_type_property(self):
        """Missing JoinType property returns UNKNOWN."""
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="OtherProp">abc</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_join_type(elem) == "UNKNOWN"

    def test_no_properties_container(self):
        """No properties element returns UNKNOWN."""
        xml_str = "<component></component>"
        elem = ET.fromstring(xml_str)
        assert _extract_join_type(elem) == "UNKNOWN"

    def test_join_type_with_whitespace(self):
        """JoinType value with surrounding whitespace is handled."""
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="JoinType"> 2 </property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_join_type(elem) == "INNER"


class TestTreatNullsAsEqual:
    """Tests for the _extract_treat_nulls_as_equal helper."""

    def test_true_value(self):
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="TreatNullsAsEqual">true</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_treat_nulls_as_equal(elem) is True

    def test_value_one(self):
        """Value '1' is treated as True."""
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="TreatNullsAsEqual">1</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_treat_nulls_as_equal(elem) is True

    def test_false_value(self):
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="TreatNullsAsEqual">false</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_treat_nulls_as_equal(elem) is False

    def test_missing_property(self):
        """Missing TreatNullsAsEqual defaults to False."""
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="JoinType">1</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_treat_nulls_as_equal(elem) is False

    def test_no_properties(self):
        """No properties container defaults to False."""
        xml_str = "<component></component>"
        elem = ET.fromstring(xml_str)
        assert _extract_treat_nulls_as_equal(elem) is False

    def test_empty_text(self):
        """Empty text value defaults to False."""
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="TreatNullsAsEqual"></property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_treat_nulls_as_equal(elem) is False

    def test_true_case_insensitive(self):
        """'True' (capitalized) is treated as True."""
        xml_str = (
            "<component>"
            "  <properties>"
            '    <property name="TreatNullsAsEqual">True</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_treat_nulls_as_equal(elem) is True


class TestJoinKeys:
    """Tests for the _extract_join_keys helper."""

    def test_single_key_pair(self):
        xml_str = (
            "<component>"
            "  <inputs>"
            '    <input refId="left" name="Left">'
            "      <inputColumns>"
            '        <inputColumn cachedName="COL_A" cachedSortKeyPosition="1"'
            '            lineageId="l1" />'
            "      </inputColumns>"
            "    </input>"
            '    <input refId="right" name="Right">'
            "      <inputColumns>"
            '        <inputColumn cachedName="COL_B" cachedSortKeyPosition="1"'
            '            lineageId="r1" />'
            "      </inputColumns>"
            "    </input>"
            "  </inputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = _extract_join_keys(elem)

        assert len(result) == 1
        assert result[0] == {
            "left_column": "COL_A",
            "right_column": "COL_B",
            "sort_key_position": 1,
        }

    def test_no_inputs(self):
        """No inputs element returns empty list."""
        xml_str = "<component></component>"
        elem = ET.fromstring(xml_str)
        assert _extract_join_keys(elem) == []

    def test_single_input_only(self):
        """Only one input (fewer than 2) returns empty list."""
        xml_str = (
            "<component>"
            "  <inputs>"
            '    <input refId="left" name="Left">'
            "      <inputColumns>"
            '        <inputColumn cachedName="COL" cachedSortKeyPosition="1"'
            '            lineageId="l1" />'
            "      </inputColumns>"
            "    </input>"
            "  </inputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_join_keys(elem) == []

    def test_no_input_columns(self):
        """Inputs with no inputColumns element returns empty list."""
        xml_str = (
            "<component>"
            "  <inputs>"
            '    <input refId="left" name="Left">'
            "    </input>"
            '    <input refId="right" name="Right">'
            "    </input>"
            "  </inputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_join_keys(elem) == []

    def test_invalid_sort_key_position_skipped(self):
        """Non-numeric cachedSortKeyPosition is skipped."""
        xml_str = (
            "<component>"
            "  <inputs>"
            '    <input refId="left" name="Left">'
            "      <inputColumns>"
            '        <inputColumn cachedName="COL" cachedSortKeyPosition="abc"'
            '            lineageId="l1" />'
            "      </inputColumns>"
            "    </input>"
            '    <input refId="right" name="Right">'
            "      <inputColumns>"
            '        <inputColumn cachedName="COL" cachedSortKeyPosition="1"'
            '            lineageId="r1" />'
            "      </inputColumns>"
            "    </input>"
            "  </inputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = _extract_join_keys(elem)

        # Only position 1 from right side found, left is empty
        assert len(result) == 1
        assert result[0]["left_column"] == ""
        assert result[0]["right_column"] == "COL"

    def test_unmatched_positions(self):
        """Key positions that only exist on one side get empty string for the other."""
        xml_str = (
            "<component>"
            "  <inputs>"
            '    <input refId="left" name="Left">'
            "      <inputColumns>"
            '        <inputColumn cachedName="LEFT_KEY1" cachedSortKeyPosition="1"'
            '            lineageId="l1" />'
            '        <inputColumn cachedName="LEFT_KEY2" cachedSortKeyPosition="2"'
            '            lineageId="l2" />'
            "      </inputColumns>"
            "    </input>"
            '    <input refId="right" name="Right">'
            "      <inputColumns>"
            '        <inputColumn cachedName="RIGHT_KEY1" cachedSortKeyPosition="1"'
            '            lineageId="r1" />'
            "      </inputColumns>"
            "    </input>"
            "  </inputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = _extract_join_keys(elem)

        assert len(result) == 2
        assert result[0]["left_column"] == "LEFT_KEY1"
        assert result[0]["right_column"] == "RIGHT_KEY1"
        assert result[0]["sort_key_position"] == 1
        assert result[1]["left_column"] == "LEFT_KEY2"
        assert result[1]["right_column"] == ""
        assert result[1]["sort_key_position"] == 2


class TestMergeJoinOutputColumns:
    """Tests for the _extract_merge_join_output_columns helper."""

    def test_extracts_output_column_attributes(self):
        """Output columns have correct attributes extracted."""
        xml_str = (
            "<component>"
            "  <outputs>"
            '    <output refId="out" name="Merge Join Output">'
            "      <outputColumns>"
            '        <outputColumn name="COL1" dataType="131"'
            '            length="0" precision="10" scale="2"'
            '            codePage="0" lineageId="100" />'
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = _extract_merge_join_output_columns(elem)

        assert len(result) == 1
        assert result[0] == {
            "name": "COL1",
            "data_type": "131",
            "length": "0",
            "precision": "10",
            "scale": "2",
            "code_page": "0",
            "lineage_id": "100",
        }

    def test_no_outputs(self):
        """No outputs element returns empty list."""
        xml_str = "<component></component>"
        elem = ET.fromstring(xml_str)
        assert _extract_merge_join_output_columns(elem) == []

    def test_only_error_output(self):
        """Only error output returns empty list."""
        xml_str = (
            "<component>"
            "  <outputs>"
            '    <output refId="err" name="Error" isErrorOut="true">'
            "      <outputColumns>"
            '        <outputColumn name="ErrorCode" dataType="3"'
            '            length="0" precision="0" scale="0"'
            '            codePage="0" lineageId="99" />'
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_merge_join_output_columns(elem) == []

    def test_no_output_columns_container(self):
        """Output without outputColumns container returns empty list."""
        xml_str = (
            "<component>"
            "  <outputs>"
            '    <output refId="out" name="Output">'
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        assert _extract_merge_join_output_columns(elem) == []

    def test_multiple_output_columns(self):
        """Multiple output columns are all extracted."""
        xml_str = (
            "<component>"
            "  <outputs>"
            '    <output refId="out" name="Merge Join Output">'
            "      <outputColumns>"
            '        <outputColumn name="ID" dataType="3"'
            '            length="0" precision="0" scale="0"'
            '            codePage="0" lineageId="1" />'
            '        <outputColumn name="NAME" dataType="130"'
            '            length="100" precision="0" scale="0"'
            '            codePage="1252" lineageId="2" />'
            '        <outputColumn name="AMOUNT" dataType="131"'
            '            length="0" precision="18" scale="2"'
            '            codePage="0" lineageId="3" />'
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = _extract_merge_join_output_columns(elem)

        assert len(result) == 3
        assert result[0]["name"] == "ID"
        assert result[1]["name"] == "NAME"
        assert result[2]["name"] == "AMOUNT"
        assert result[2]["precision"] == "18"
        assert result[2]["scale"] == "2"


class TestComponentIntegration:
    """Tests for merge join extraction integrated with extract_component."""

    def test_merge_join_component_has_join_fields(self):
        """extract_component adds merge join fields for MergeJoin components."""
        xml_str = (
            '<component refId="Package\\DFT\\Merge Join" name="Merge Join"'
            ' componentClassID="Microsoft.MergeJoin"'
            ' version="1" usesDispositions="true">'
            "  <properties>"
            '    <property name="JoinType">2</property>'
            '    <property name="TreatNullsAsEqual">true</property>'
            "  </properties>"
            "  <inputs>"
            '    <input refId="left" name="Merge Join Left Input">'
            "      <inputColumns>"
            '        <inputColumn refId="lc1"'
            '            cachedName="PROJECT_ID"'
            '            cachedDataType="131"'
            '            cachedSortKeyPosition="1"'
            '            lineageId="src1.Out.PROJECT_ID" />'
            "      </inputColumns>"
            "    </input>"
            '    <input refId="right" name="Merge Join Right Input">'
            "      <inputColumns>"
            '        <inputColumn refId="rc1"'
            '            cachedName="PROJECT_ID"'
            '            cachedDataType="131"'
            '            cachedSortKeyPosition="1"'
            '            lineageId="src2.Out.PROJECT_ID" />'
            "      </inputColumns>"
            "    </input>"
            "  </inputs>"
            "  <outputs>"
            '    <output refId="out" name="Merge Join Output">'
            "      <outputColumns>"
            '        <outputColumn name="PROJECT_ID" dataType="131"'
            '            length="0" precision="10" scale="0"'
            '            codePage="0" lineageId="42" />'
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["classification"] == "transformation"
        assert result["component_class_id"] == "Microsoft.MergeJoin"
        assert result["join_type"] == "INNER"
        assert result["treat_nulls_as_equal"] is True
        assert len(result["join_keys"]) == 1
        assert result["join_keys"][0] == {
            "left_column": "PROJECT_ID",
            "right_column": "PROJECT_ID",
            "sort_key_position": 1,
        }
        assert len(result["output_columns"]) == 1
        assert result["output_columns"][0]["name"] == "PROJECT_ID"

    def test_merge_join_with_no_configured_keys(self):
        """MergeJoin with no configured keys has empty join_keys (Req 10.6)."""
        xml_str = (
            '<component refId="Package\\DFT\\MJ" name="Merge Join"'
            ' componentClassID="Microsoft.MergeJoin">'
            "  <properties>"
            '    <property name="JoinType">1</property>'
            '    <property name="TreatNullsAsEqual">false</property>'
            "  </properties>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["classification"] == "transformation"
        assert result["join_type"] == "LEFT"
        assert result["treat_nulls_as_equal"] is False
        assert result["join_keys"] == []
        assert result["output_columns"] == []

    def test_non_merge_join_component_no_join_fields(self):
        """Non-MergeJoin components do not have join_type or join_keys."""
        xml_str = (
            '<component refId="Package\\DFT\\Src" name="Source"'
            ' componentClassID="Microsoft.OLEDBSource">'
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert "join_type" not in result
        assert "join_keys" not in result
        assert "treat_nulls_as_equal" not in result

    def test_real_world_structure(self):
        """Test with a structure matching real SSIS merge join XML."""
        xml_str = (
            "<component"
            '  refId="Package\\Application Person 1\\Merge Join"'
            '  componentClassID="Microsoft.MergeJoin"'
            '  contactInfo="Merge Join;Microsoft Corporation"'
            '  description="Combine two sorted data flows"'
            '  name="Merge Join"'
            '  version="1">'
            "  <properties>"
            '    <property dataType="System.Int32" name="JoinType">2</property>'
            '    <property dataType="System.Int32" name="NumKeyColumns">1</property>'
            '    <property dataType="System.Boolean"'
            '        name="TreatNullsAsEqual">true</property>'
            '    <property dataType="System.Int32"'
            '        name="MaxBuffersPerInput">5</property>'
            "  </properties>"
            "  <inputs>"
            '    <input refId="left" hasSideEffects="true"'
            '        name="Merge Join Left Input">'
            "      <inputColumns>"
            "        <inputColumn"
            '            cachedCodepage="1252"'
            '            cachedDataType="str"'
            '            cachedLength="50"'
            '            cachedName="LEGACY_PROJECT_IDENTIFIER"'
            '            cachedSortKeyPosition="1"'
            '            lineageId="Sort1.Out.LEGACY_PROJECT_IDENTIFIER"'
            '            refId="lc1" />'
            "      </inputColumns>"
            "      <externalMetadataColumns />"
            "    </input>"
            '    <input refId="right" hasSideEffects="true"'
            '        name="Merge Join Right Input">'
            "      <inputColumns>"
            "        <inputColumn"
            '            cachedCodepage="1252"'
            '            cachedDataType="str"'
            '            cachedLength="10"'
            '            cachedName="ProjectIdentifier"'
            '            cachedSortKeyPosition="1"'
            '            lineageId="Sort2.Out.ProjectIdentifier"'
            '            refId="rc1" />'
            "        <inputColumn"
            '            cachedCodepage="1252"'
            '            cachedDataType="str"'
            '            cachedLength="10"'
            '            cachedName="CCODE"'
            '            lineageId="Sort2.Out.CCODE"'
            '            refId="rc2" />'
            "      </inputColumns>"
            "      <externalMetadataColumns />"
            "    </input>"
            "  </inputs>"
            "  <outputs>"
            '    <output refId="out" isSorted="true" name="Merge Join Output">'
            "      <outputColumns>"
            '        <outputColumn codePage="1252" dataType="str"'
            '            length="50"'
            '            lineageId="MJ.Out.LEGACY_PROJECT_IDENTIFIER"'
            '            name="LEGACY_PROJECT_IDENTIFIER"'
            '            precision="0" scale="0" />'
            '        <outputColumn codePage="1252" dataType="str"'
            '            length="10"'
            '            lineageId="MJ.Out.CCODE"'
            '            name="CCODE"'
            '            precision="0" scale="0" />'
            "      </outputColumns>"
            "    </output>"
            "  </outputs>"
            "</component>"
        )
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["join_type"] == "INNER"
        assert result["treat_nulls_as_equal"] is True
        assert len(result["join_keys"]) == 1
        assert result["join_keys"][0]["left_column"] == "LEGACY_PROJECT_IDENTIFIER"
        assert result["join_keys"][0]["right_column"] == "ProjectIdentifier"
        assert result["join_keys"][0]["sort_key_position"] == 1
        assert len(result["output_columns"]) == 2
        assert result["output_columns"][0]["name"] == "LEGACY_PROJECT_IDENTIFIER"
        assert result["output_columns"][1]["name"] == "CCODE"
