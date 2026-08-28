"""Unit tests for precedence constraint extraction."""

import xml.etree.ElementTree as ET

import pytest

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.errors import ExtractionError
from pydtsx_parser.extractors.precedence import extract_precedence_constraints

DTS_NS = NAMESPACES["DTS"]


def _make_package_with_constraints(constraints_xml: str) -> ET.Element:
    """Build a minimal package element with DTS:PrecedenceConstraints."""
    xml_str = (
        f'<DTS:Executable xmlns:DTS="{DTS_NS}">  {constraints_xml}</DTS:Executable>'
    )
    return ET.fromstring(xml_str)


class TestEmptyConstraints:
    """Requirement 9.5: empty or missing constraints return empty list."""

    def test_no_precedence_constraints_element(self):
        """No DTS:PrecedenceConstraints element returns empty list."""
        xml_str = f'<DTS:Executable xmlns:DTS="{DTS_NS}"></DTS:Executable>'
        root = ET.fromstring(xml_str)
        result = extract_precedence_constraints(root, "test.dtsx")
        assert result == []

    def test_empty_precedence_constraints_element(self):
        """Empty DTS:PrecedenceConstraints element returns empty list."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints></DTS:PrecedenceConstraints>"
        )
        result = extract_precedence_constraints(root, "test.dtsx")
        assert result == []


class TestBasicExtraction:
    """Requirement 9.1: extract basic constraint attributes."""

    def test_single_constraint(self):
        """Extract a single precedence constraint with all attributes."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="Package.PrecedenceConstraints[Constraint]"'
            '    DTS:CreationName=""'
            '    DTS:DTSID="{826A86A2-0FBB-4833-9D33-EEE60317E7B8}"'
            '    DTS:From="Package\\Truncate Tables"'
            '    DTS:LogicalAnd="True"'
            '    DTS:ObjectName="Constraint"'
            '    DTS:To="Package\\Load Tables" />'
            "</DTS:PrecedenceConstraints>"
        )
        result = extract_precedence_constraints(root, "test.dtsx")

        assert len(result) == 1
        constraint = result[0]
        assert constraint["ref_id"] == "Package.PrecedenceConstraints[Constraint]"
        assert constraint["dts_id"] == "{826A86A2-0FBB-4833-9D33-EEE60317E7B8}"
        assert constraint["object_name"] == "Constraint"
        assert constraint["from_task"] == "Package\\Truncate Tables"
        assert constraint["to_task"] == "Package\\Load Tables"
        assert constraint["logical_and"] is True
        assert constraint["eval_op"] == "Constraint"
        assert constraint["expression"] == ""
        assert constraint["value"] == "Success"

    def test_multiple_constraints(self):
        """Extract multiple precedence constraints."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="Package.PrecedenceConstraints[Constraint]"'
            '    DTS:DTSID="{AAA}"'
            '    DTS:From="Package\\TaskA"'
            '    DTS:LogicalAnd="True"'
            '    DTS:ObjectName="Constraint"'
            '    DTS:To="Package\\TaskB" />'
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="Package.PrecedenceConstraints[Constraint 1]"'
            '    DTS:DTSID="{BBB}"'
            '    DTS:From="Package\\TaskB"'
            '    DTS:LogicalAnd="True"'
            '    DTS:ObjectName="Constraint 1"'
            '    DTS:To="Package\\TaskC" />'
            "</DTS:PrecedenceConstraints>"
        )
        result = extract_precedence_constraints(root, "test.dtsx")

        assert len(result) == 2
        assert result[0]["from_task"] == "Package\\TaskA"
        assert result[0]["to_task"] == "Package\\TaskB"
        assert result[1]["from_task"] == "Package\\TaskB"
        assert result[1]["to_task"] == "Package\\TaskC"


class TestLogicalAnd:
    """Requirement 9.4: LogicalAnd attribute for AND/OR logic."""

    def test_logical_and_true(self):
        """LogicalAnd='True' maps to True."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="ref1"'
            '    DTS:DTSID="{ID1}"'
            '    DTS:From="Package\\A"'
            '    DTS:LogicalAnd="True"'
            '    DTS:ObjectName="C1"'
            '    DTS:To="Package\\B" />'
            "</DTS:PrecedenceConstraints>"
        )
        result = extract_precedence_constraints(root, "test.dtsx")
        assert result[0]["logical_and"] is True

    def test_logical_and_false(self):
        """LogicalAnd='False' maps to False (OR logic)."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="ref1"'
            '    DTS:DTSID="{ID1}"'
            '    DTS:From="Package\\A"'
            '    DTS:LogicalAnd="False"'
            '    DTS:ObjectName="C1"'
            '    DTS:To="Package\\B" />'
            "</DTS:PrecedenceConstraints>"
        )
        result = extract_precedence_constraints(root, "test.dtsx")
        assert result[0]["logical_and"] is False

    def test_logical_and_defaults_to_true(self):
        """Missing LogicalAnd attribute defaults to True."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="ref1"'
            '    DTS:DTSID="{ID1}"'
            '    DTS:From="Package\\A"'
            '    DTS:ObjectName="C1"'
            '    DTS:To="Package\\B" />'
            "</DTS:PrecedenceConstraints>"
        )
        result = extract_precedence_constraints(root, "test.dtsx")
        assert result[0]["logical_and"] is True


class TestExpressionEvaluation:
    """Requirement 9.2: expression-based evaluation extraction."""

    def test_expression_eval_op(self):
        """EvalOp='Expression' with expression text."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="ref1"'
            '    DTS:DTSID="{ID1}"'
            '    DTS:From="Package\\A"'
            '    DTS:To="Package\\B"'
            '    DTS:ObjectName="C1"'
            '    DTS:LogicalAnd="True"'
            '    DTS:EvalOp="Expression"'
            '    DTS:Expression="@[User::Flag] == 1" />'
            "</DTS:PrecedenceConstraints>"
        )
        result = extract_precedence_constraints(root, "test.dtsx")
        constraint = result[0]
        assert constraint["eval_op"] == "Expression"
        assert constraint["expression"] == "@[User::Flag] == 1"

    def test_expression_and_constraint(self):
        """EvalOp='ExpressionAndConstraint' with value and expression."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="ref1"'
            '    DTS:DTSID="{ID1}"'
            '    DTS:From="Package\\A"'
            '    DTS:To="Package\\B"'
            '    DTS:ObjectName="C1"'
            '    DTS:LogicalAnd="True"'
            '    DTS:EvalOp="ExpressionAndConstraint"'
            '    DTS:Expression="@[User::RunMode] == &quot;Full&quot;"'
            '    DTS:Value="0" />'
            "</DTS:PrecedenceConstraints>"
        )
        result = extract_precedence_constraints(root, "test.dtsx")
        constraint = result[0]
        assert constraint["eval_op"] == "ExpressionAndConstraint"
        assert constraint["expression"] == '@[User::RunMode] == "Full"'
        assert constraint["value"] == "Success"

    def test_expression_or_constraint(self):
        """EvalOp='ExpressionOrConstraint' with failure value."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="ref1"'
            '    DTS:DTSID="{ID1}"'
            '    DTS:From="Package\\A"'
            '    DTS:To="Package\\B"'
            '    DTS:ObjectName="C1"'
            '    DTS:LogicalAnd="True"'
            '    DTS:EvalOp="ExpressionOrConstraint"'
            '    DTS:Expression="@[User::AlwaysRun] == True"'
            '    DTS:Value="1" />'
            "</DTS:PrecedenceConstraints>"
        )
        result = extract_precedence_constraints(root, "test.dtsx")
        constraint = result[0]
        assert constraint["eval_op"] == "ExpressionOrConstraint"
        assert constraint["value"] == "Failure"


class TestConstraintValues:
    """Test constraint value mapping (Success, Failure, Completion)."""

    def test_value_success(self):
        """Value='0' maps to 'Success'."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="ref1"'
            '    DTS:DTSID="{ID1}"'
            '    DTS:From="Package\\A"'
            '    DTS:To="Package\\B"'
            '    DTS:ObjectName="C1"'
            '    DTS:Value="0" />'
            "</DTS:PrecedenceConstraints>"
        )
        result = extract_precedence_constraints(root, "test.dtsx")
        assert result[0]["value"] == "Success"

    def test_value_failure(self):
        """Value='1' maps to 'Failure'."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="ref1"'
            '    DTS:DTSID="{ID1}"'
            '    DTS:From="Package\\A"'
            '    DTS:To="Package\\B"'
            '    DTS:ObjectName="C1"'
            '    DTS:Value="1" />'
            "</DTS:PrecedenceConstraints>"
        )
        result = extract_precedence_constraints(root, "test.dtsx")
        assert result[0]["value"] == "Failure"

    def test_value_completion(self):
        """Value='2' maps to 'Completion'."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="ref1"'
            '    DTS:DTSID="{ID1}"'
            '    DTS:From="Package\\A"'
            '    DTS:To="Package\\B"'
            '    DTS:ObjectName="C1"'
            '    DTS:Value="2" />'
            "</DTS:PrecedenceConstraints>"
        )
        result = extract_precedence_constraints(root, "test.dtsx")
        assert result[0]["value"] == "Completion"

    def test_value_default_success(self):
        """Missing Value attribute defaults to 'Success' (code 0)."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="ref1"'
            '    DTS:DTSID="{ID1}"'
            '    DTS:From="Package\\A"'
            '    DTS:To="Package\\B"'
            '    DTS:ObjectName="C1" />'
            "</DTS:PrecedenceConstraints>"
        )
        result = extract_precedence_constraints(root, "test.dtsx")
        assert result[0]["value"] == "Success"


class TestMalformedConstraints:
    """Requirement 9.6: malformed constraints raise ExtractionError."""

    def test_missing_from_attribute(self):
        """Missing DTS:From raises ExtractionError."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="ref1"'
            '    DTS:DTSID="{ID1}"'
            '    DTS:ObjectName="C1"'
            '    DTS:To="Package\\B" />'
            "</DTS:PrecedenceConstraints>"
        )
        with pytest.raises(ExtractionError) as exc_info:
            extract_precedence_constraints(root, "test.dtsx")
        assert "DTS:From" in exc_info.value.reason
        assert exc_info.value.file_path == "test.dtsx"

    def test_missing_to_attribute(self):
        """Missing DTS:To raises ExtractionError."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="ref1"'
            '    DTS:DTSID="{ID1}"'
            '    DTS:ObjectName="C1"'
            '    DTS:From="Package\\A" />'
            "</DTS:PrecedenceConstraints>"
        )
        with pytest.raises(ExtractionError) as exc_info:
            extract_precedence_constraints(root, "test.dtsx")
        assert "DTS:To" in exc_info.value.reason

    def test_missing_both_from_and_to(self):
        """Missing both DTS:From and DTS:To raises ExtractionError."""
        root = _make_package_with_constraints(
            "<DTS:PrecedenceConstraints>"
            "  <DTS:PrecedenceConstraint"
            '    DTS:refId="ref1"'
            '    DTS:DTSID="{ID1}"'
            '    DTS:ObjectName="C1" />'
            "</DTS:PrecedenceConstraints>"
        )
        with pytest.raises(ExtractionError) as exc_info:
            extract_precedence_constraints(root, "test.dtsx")
        assert "DTS:From" in exc_info.value.reason
        assert "DTS:To" in exc_info.value.reason
