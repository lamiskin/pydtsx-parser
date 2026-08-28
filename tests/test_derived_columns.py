"""Unit tests for derived column extraction from DerivedColumn components."""

import xml.etree.ElementTree as ET

import pytest

from pydtsx_parser.extractors.components import extract_component
from pydtsx_parser.extractors.transformations import extract_derived_columns


class TestExtractNewDerivedColumns:
    """Test extraction of new derived columns from output columns."""

    def test_single_new_column(self):
        """A single new derived column is extracted with full metadata."""
        xml_str = """
        <component refId="Package\\DFT\\DC" name="Derived Column"
            componentClassID="Microsoft.DerivedColumn" usesDispositions="true">
            <inputs>
                <input refId="Package\\DFT\\DC.Inputs[Input]" name="Derived Column Input">
                    <inputColumns />
                    <externalMetadataColumns />
                </input>
            </inputs>
            <outputs>
                <output refId="Package\\DFT\\DC.Outputs[Output]"
                    name="Derived Column Output">
                    <outputColumns>
                        <outputColumn refId="out1" name="CLEAN_TITLE"
                            dataType="str" length="4000" precision="0"
                            scale="0" codePage="1252"
                            lineageId="out1">
                            <properties>
                                <property name="Expression">REPLACE(Title,"\\r","")</property>
                                <property name="FriendlyExpression">REPLACE(Title,CRLF,"")</property>
                            </properties>
                        </outputColumn>
                    </outputColumns>
                </output>
            </outputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert "derived_columns" in result
        assert len(result["derived_columns"]) == 1

        col = result["derived_columns"][0]
        assert col["column_name"] == "CLEAN_TITLE"
        assert col["expression"] == 'REPLACE(Title,"\\r","")'
        assert col["friendly_expression"] == 'REPLACE(Title,CRLF,"")'
        assert col["data_type"] == "str"
        assert col["length"] == "4000"
        assert col["precision"] == "0"
        assert col["scale"] == "0"
        assert col["code_page"] == "1252"
        assert col["is_overwrite"] is False

    def test_multiple_new_columns(self):
        """Multiple new derived columns are all extracted."""
        xml_str = """
        <component refId="Package\\DFT\\DC" name="Strip CRLF"
            componentClassID="Microsoft.DerivedColumn" usesDispositions="true">
            <inputs>
                <input refId="in1" name="Derived Column Input">
                    <inputColumns />
                </input>
            </inputs>
            <outputs>
                <output refId="out1" name="Derived Column Output">
                    <outputColumns>
                        <outputColumn refId="c1" name="COL_A"
                            dataType="wstr" length="100" precision="0"
                            scale="0" codePage="0">
                            <properties>
                                <property name="Expression">UPPER(COL_A)</property>
                                <property name="FriendlyExpression">UPPER(COL_A)</property>
                            </properties>
                        </outputColumn>
                        <outputColumn refId="c2" name="COL_B"
                            dataType="i4" length="0" precision="10"
                            scale="2" codePage="0">
                            <properties>
                                <property name="Expression">COL_B * 2</property>
                                <property name="FriendlyExpression">COL_B * 2</property>
                            </properties>
                        </outputColumn>
                    </outputColumns>
                </output>
            </outputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert len(result["derived_columns"]) == 2
        assert result["derived_columns"][0]["column_name"] == "COL_A"
        assert result["derived_columns"][1]["column_name"] == "COL_B"
        assert result["derived_columns"][1]["data_type"] == "i4"
        assert result["derived_columns"][1]["precision"] == "10"
        assert result["derived_columns"][1]["scale"] == "2"

    def test_error_output_columns_excluded(self):
        """Columns from error outputs are not included in derived_columns."""
        xml_str = """
        <component refId="Package\\DFT\\DC" name="DC"
            componentClassID="Microsoft.DerivedColumn">
            <outputs>
                <output refId="out1" name="Derived Column Output">
                    <outputColumns>
                        <outputColumn refId="c1" name="NEW_COL"
                            dataType="wstr" length="50" precision="0"
                            scale="0" codePage="0">
                            <properties>
                                <property name="Expression">"hello"</property>
                                <property name="FriendlyExpression">"hello"</property>
                            </properties>
                        </outputColumn>
                    </outputColumns>
                </output>
                <output refId="err1" name="Error Output" isErrorOut="true">
                    <outputColumns>
                        <outputColumn refId="e1" name="ErrorCode" dataType="i4">
                            <properties>
                                <property name="Expression">SHOULD_NOT_APPEAR</property>
                            </properties>
                        </outputColumn>
                    </outputColumns>
                </output>
            </outputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert len(result["derived_columns"]) == 1
        assert result["derived_columns"][0]["column_name"] == "NEW_COL"

    def test_no_derived_columns_empty_list(self):
        """DerivedColumn with no configured columns returns empty list."""
        xml_str = """
        <component refId="Package\\DFT\\DC" name="Empty DC"
            componentClassID="Microsoft.DerivedColumn">
            <outputs>
                <output refId="out1" name="Derived Column Output">
                    <outputColumns />
                </output>
            </outputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert "derived_columns" in result
        assert result["derived_columns"] == []

    def test_output_column_without_expression_skipped(self):
        """Output columns without Expression property are not included."""
        xml_str = """
        <component refId="Package\\DFT\\DC" name="DC"
            componentClassID="Microsoft.DerivedColumn">
            <outputs>
                <output refId="out1" name="Derived Column Output">
                    <outputColumns>
                        <outputColumn refId="c1" name="HAS_EXPR"
                            dataType="wstr" length="50" precision="0"
                            scale="0" codePage="0">
                            <properties>
                                <property name="Expression">UPPER(X)</property>
                                <property name="FriendlyExpression">UPPER(X)</property>
                            </properties>
                        </outputColumn>
                        <outputColumn refId="c2" name="NO_EXPR"
                            dataType="wstr" length="50" precision="0"
                            scale="0" codePage="0">
                        </outputColumn>
                    </outputColumns>
                </output>
            </outputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert len(result["derived_columns"]) == 1
        assert result["derived_columns"][0]["column_name"] == "HAS_EXPR"


class TestExtractOverwriteColumns:
    """Test extraction of overwrite derived columns from input columns."""

    def test_single_overwrite_column(self):
        """An overwrite column with usageType=readWrite is extracted."""
        xml_str = """
        <component refId="Package\\DFT\\DC" name="DC"
            componentClassID="Microsoft.DerivedColumn" usesDispositions="true">
            <inputs>
                <input refId="in1" name="Derived Column Input">
                    <inputColumns>
                        <inputColumn refId="ic1" cachedName="EXISTING_COL"
                            cachedDataType="str" cachedLength="200"
                            lineageId="Package\\Upstream.Outputs[Out].Columns[EXISTING_COL]"
                            usageType="readWrite">
                            <properties>
                                <property name="Expression">UPPER(EXISTING_COL)</property>
                                <property name="FriendlyExpression">UPPER(EXISTING_COL)</property>
                            </properties>
                        </inputColumn>
                    </inputColumns>
                </input>
            </inputs>
            <outputs>
                <output refId="out1" name="Derived Column Output">
                    <outputColumns />
                </output>
            </outputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert "derived_columns" in result
        overwrite_cols = [c for c in result["derived_columns"] if c["is_overwrite"]]
        assert len(overwrite_cols) == 1

        col = overwrite_cols[0]
        assert col["column_name"] == "EXISTING_COL"
        assert col["expression"] == "UPPER(EXISTING_COL)"
        assert col["friendly_expression"] == "UPPER(EXISTING_COL)"
        assert (
            col["original_lineage_id"]
            == "Package\\Upstream.Outputs[Out].Columns[EXISTING_COL]"
        )
        assert col["is_overwrite"] is True

    def test_mixed_new_and_overwrite_columns(self):
        """Both new and overwrite columns are extracted together."""
        xml_str = """
        <component refId="Package\\DFT\\DC" name="Mixed DC"
            componentClassID="Microsoft.DerivedColumn" usesDispositions="true">
            <inputs>
                <input refId="in1" name="Derived Column Input">
                    <inputColumns>
                        <inputColumn refId="ic1" cachedName="OVERWRITTEN"
                            cachedDataType="str" cachedLength="100"
                            lineageId="upstream_lineage_55"
                            usageType="readWrite">
                            <properties>
                                <property name="Expression">TRIM(OVERWRITTEN)</property>
                                <property name="FriendlyExpression">TRIM(OVERWRITTEN)</property>
                            </properties>
                        </inputColumn>
                        <inputColumn refId="ic2" cachedName="READ_ONLY"
                            cachedDataType="str" cachedLength="50"
                            lineageId="upstream_lineage_42" />
                    </inputColumns>
                </input>
            </inputs>
            <outputs>
                <output refId="out1" name="Derived Column Output">
                    <outputColumns>
                        <outputColumn refId="oc1" name="NEW_COL"
                            dataType="wstr" length="200" precision="0"
                            scale="0" codePage="0">
                            <properties>
                                <property name="Expression">"constant"</property>
                                <property name="FriendlyExpression">"constant"</property>
                            </properties>
                        </outputColumn>
                    </outputColumns>
                </output>
            </outputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert len(result["derived_columns"]) == 2

        overwrites = [c for c in result["derived_columns"] if c["is_overwrite"]]
        new_cols = [c for c in result["derived_columns"] if not c["is_overwrite"]]

        assert len(overwrites) == 1
        assert overwrites[0]["column_name"] == "OVERWRITTEN"
        assert overwrites[0]["original_lineage_id"] == "upstream_lineage_55"

        assert len(new_cols) == 1
        assert new_cols[0]["column_name"] == "NEW_COL"
        assert new_cols[0]["data_type"] == "wstr"

    def test_non_readwrite_input_columns_ignored(self):
        """Input columns without usageType=readWrite are not extracted as overwrites."""
        xml_str = """
        <component refId="Package\\DFT\\DC" name="DC"
            componentClassID="Microsoft.DerivedColumn">
            <inputs>
                <input refId="in1" name="Derived Column Input">
                    <inputColumns>
                        <inputColumn refId="ic1" cachedName="PASS_THROUGH"
                            cachedDataType="str" cachedLength="100"
                            lineageId="upstream_42" />
                    </inputColumns>
                </input>
            </inputs>
            <outputs>
                <output refId="out1" name="Derived Column Output">
                    <outputColumns />
                </output>
            </outputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["derived_columns"] == []


class TestDerivedColumnFailure:
    """Test that extraction fails entirely when required overwrite elements are missing."""

    def test_overwrite_missing_lineage_id_fails(self):
        """Missing lineageId on readWrite inputColumn causes extraction failure."""
        xml_str = """
        <component refId="Package\\DFT\\DC" name="Bad DC"
            componentClassID="Microsoft.DerivedColumn">
            <inputs>
                <input refId="in1" name="Derived Column Input">
                    <inputColumns>
                        <inputColumn refId="ic1" cachedName="COL"
                            cachedDataType="str" cachedLength="100"
                            usageType="readWrite">
                            <properties>
                                <property name="Expression">UPPER(COL)</property>
                                <property name="FriendlyExpression">UPPER(COL)</property>
                            </properties>
                        </inputColumn>
                    </inputColumns>
                </input>
            </inputs>
            <outputs>
                <output refId="out1" name="Derived Column Output">
                    <outputColumns />
                </output>
            </outputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["extraction_status"] == "failed"
        assert "lineageId" in result["failure_reason"]

    def test_overwrite_missing_expression_fails(self):
        """Missing Expression property on readWrite inputColumn causes extraction failure."""
        xml_str = """
        <component refId="Package\\DFT\\DC" name="Bad DC"
            componentClassID="Microsoft.DerivedColumn">
            <inputs>
                <input refId="in1" name="Derived Column Input">
                    <inputColumns>
                        <inputColumn refId="ic1" cachedName="COL"
                            cachedDataType="str" cachedLength="100"
                            lineageId="upstream_55"
                            usageType="readWrite">
                            <properties>
                                <property name="FriendlyExpression">UPPER(COL)</property>
                            </properties>
                        </inputColumn>
                    </inputColumns>
                </input>
            </inputs>
            <outputs>
                <output refId="out1" name="Derived Column Output">
                    <outputColumns />
                </output>
            </outputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["extraction_status"] == "failed"
        assert "Expression" in result["failure_reason"]

    def test_overwrite_missing_properties_element_fails(self):
        """Missing properties element on readWrite inputColumn causes extraction failure."""
        xml_str = """
        <component refId="Package\\DFT\\DC" name="Bad DC"
            componentClassID="Microsoft.DerivedColumn">
            <inputs>
                <input refId="in1" name="Derived Column Input">
                    <inputColumns>
                        <inputColumn refId="ic1" cachedName="COL"
                            cachedDataType="str" cachedLength="100"
                            lineageId="upstream_55"
                            usageType="readWrite">
                        </inputColumn>
                    </inputColumns>
                </input>
            </inputs>
            <outputs>
                <output refId="out1" name="Derived Column Output">
                    <outputColumns />
                </output>
            </outputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["extraction_status"] == "failed"
        assert "properties" in result["failure_reason"].lower()

    def test_failure_preserves_ref_id_and_name(self):
        """Failed extraction still reports ref_id and name."""
        xml_str = """
        <component refId="Package\\DFT\\MyComponent" name="My Derived Col"
            componentClassID="Microsoft.DerivedColumn">
            <inputs>
                <input refId="in1" name="Input">
                    <inputColumns>
                        <inputColumn refId="ic1" cachedName="COL"
                            usageType="readWrite">
                        </inputColumn>
                    </inputColumns>
                </input>
            </inputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert result["extraction_status"] == "failed"
        assert result["ref_id"] == "Package\\DFT\\MyComponent"
        assert result["name"] == "My Derived Col"


class TestDerivedColumnIntegration:
    """Integration tests ensuring extract_component enriches DerivedColumn."""

    def test_component_result_has_standard_fields_and_derived_columns(self):
        """Successful DerivedColumn extraction includes both standard and derived fields."""
        xml_str = """
        <component refId="Package\\DFT\\DC" name="My DC"
            componentClassID="Microsoft.DerivedColumn" contactInfo="info"
            version="1" usesDispositions="true">
            <inputs>
                <input refId="in1" name="Derived Column Input">
                    <inputColumns />
                </input>
            </inputs>
            <outputs>
                <output refId="out1" name="Derived Column Output">
                    <outputColumns>
                        <outputColumn refId="oc1" name="NEW"
                            dataType="wstr" length="100" precision="0"
                            scale="0" codePage="0">
                            <properties>
                                <property name="Expression">UPPER(X)</property>
                                <property name="FriendlyExpression">UPPER(X)</property>
                            </properties>
                        </outputColumn>
                    </outputColumns>
                </output>
            </outputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        # Standard fields still present
        assert result["ref_id"] == "Package\\DFT\\DC"
        assert result["name"] == "My DC"
        assert result["component_class_id"] == "Microsoft.DerivedColumn"
        assert result["classification"] == "transformation"
        assert result["contact_info"] == "info"
        assert result["version"] == "1"
        assert result["uses_dispositions"] is True
        assert "inputs" in result
        assert "outputs" in result

        # Derived columns also present
        assert "derived_columns" in result
        assert len(result["derived_columns"]) == 1

    def test_non_derived_column_component_has_no_derived_columns_key(self):
        """Non-DerivedColumn components do not get a derived_columns key."""
        xml_str = """
        <component refId="Package\\DFT\\Sort" name="Sort"
            componentClassID="Microsoft.ConditionalSplit">
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        assert "derived_columns" not in result

    def test_empty_expression_text_is_skipped(self):
        """An Expression with empty text is not a valid derived column and is skipped."""
        xml_str = """
        <component refId="Package\\DFT\\DC" name="DC"
            componentClassID="Microsoft.DerivedColumn">
            <outputs>
                <output refId="out1" name="Derived Column Output">
                    <outputColumns>
                        <outputColumn refId="oc1" name="EMPTY_EXPR"
                            dataType="wstr" length="50" precision="0"
                            scale="0" codePage="0">
                            <properties>
                                <property name="Expression"></property>
                                <property name="FriendlyExpression"></property>
                            </properties>
                        </outputColumn>
                    </outputColumns>
                </output>
            </outputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_component(elem)

        # Empty expression means no valid derived column - it's skipped
        assert result["derived_columns"] == []


class TestExtractDerivedColumnsDirectly:
    """Test the extract_derived_columns function directly."""

    def test_raises_value_error_on_missing_lineage_id(self):
        """ValueError is raised when overwrite column lacks lineageId."""
        xml_str = """
        <component refId="test" name="test"
            componentClassID="Microsoft.DerivedColumn">
            <inputs>
                <input refId="in1" name="Input">
                    <inputColumns>
                        <inputColumn refId="ic1" cachedName="COL"
                            usageType="readWrite">
                            <properties>
                                <property name="Expression">X</property>
                            </properties>
                        </inputColumn>
                    </inputColumns>
                </input>
            </inputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        with pytest.raises(ValueError, match="lineageId"):
            extract_derived_columns(elem)

    def test_raises_value_error_on_missing_expression(self):
        """ValueError is raised when overwrite column lacks Expression."""
        xml_str = """
        <component refId="test" name="test"
            componentClassID="Microsoft.DerivedColumn">
            <inputs>
                <input refId="in1" name="Input">
                    <inputColumns>
                        <inputColumn refId="ic1" cachedName="COL"
                            lineageId="upstream_55"
                            usageType="readWrite">
                            <properties>
                                <property name="FriendlyExpression">X</property>
                            </properties>
                        </inputColumn>
                    </inputColumns>
                </input>
            </inputs>
        </component>
        """
        elem = ET.fromstring(xml_str)
        with pytest.raises(ValueError, match="Expression"):
            extract_derived_columns(elem)

    def test_no_inputs_returns_empty(self):
        """Component with no inputs returns empty derived_columns."""
        xml_str = """
        <component refId="test" name="test"
            componentClassID="Microsoft.DerivedColumn">
        </component>
        """
        elem = ET.fromstring(xml_str)
        result = extract_derived_columns(elem)
        assert result == {"derived_columns": []}
