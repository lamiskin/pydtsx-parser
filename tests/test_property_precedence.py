"""Property-based tests for precedence constraint extraction.

Uses Hypothesis to verify correctness properties of the precedence constraint
extractor by generating random constraint graphs and verifying structural
properties of the extraction output.

# Feature: pydtsx-parser, Property 11: Precedence Constraint Graph Completeness

**Validates: Requirements 9.1, 9.2, 9.3, 9.4**
"""

import xml.etree.ElementTree as ET

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pydtsx_parser.extractors.precedence import extract_precedence_constraints

# DTS namespace used in SSIS files
DTS_NS = "www.microsoft.com/SqlServer/Dts"

# Valid EvalOp values
_EVAL_OPS = [
    "Constraint",
    "Expression",
    "ExpressionAndConstraint",
    "ExpressionOrConstraint",
]

# Constraint value codes and their expected mapped outputs
_CONSTRAINT_VALUE_CODES = ["0", "1", "2"]
_CONSTRAINT_VALUE_MAP = {
    "0": "Success",
    "1": "Failure",
    "2": "Completion",
}


# --- Strategies ---

# Strategy for generating safe identifier strings (used for task names, refIds, etc.)
safe_identifier = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters=r"_-.\\ {}",
    ),
    min_size=1,
    max_size=30,
)

# Strategy for DTSID-like strings (GUID format)
dts_id = st.builds(
    lambda s: f"{{{s}}}",
    st.text(
        alphabet=st.characters(
            whitelist_categories=("N",), whitelist_characters="ABCDEF-"
        ),
        min_size=8,
        max_size=36,
    ),
)

# Strategy for expression text
expression_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters="@[] ==!<>()_ \"'",
    ),
    min_size=1,
    max_size=50,
)

# Strategy for LogicalAnd values
logical_and_value = st.sampled_from(["True", "False"])

# Strategy for EvalOp
eval_op_value = st.sampled_from(_EVAL_OPS)

# Strategy for constraint value codes
constraint_value_code = st.sampled_from(_CONSTRAINT_VALUE_CODES)


# Strategy for a single constraint's data
@st.composite
def constraint_data(draw):
    """Generate data for a single precedence constraint."""
    ref_id = draw(safe_identifier)
    dtsid = draw(dts_id)
    object_name = draw(safe_identifier)
    from_task = draw(
        st.builds(
            lambda pkg, task: f"Package\\\\{task}",
            st.just("Package"),
            safe_identifier,
        )
    )
    to_task = draw(
        st.builds(
            lambda pkg, task: f"Package\\\\{task}",
            st.just("Package"),
            safe_identifier,
        )
    )
    logical_and = draw(logical_and_value)
    eval_op = draw(eval_op_value)
    value = draw(constraint_value_code)

    # Only generate expression text for expression-based EvalOps
    if eval_op in ("Expression", "ExpressionAndConstraint", "ExpressionOrConstraint"):
        expression = draw(expression_text)
    else:
        expression = ""

    return {
        "ref_id": ref_id,
        "dts_id": dtsid,
        "object_name": object_name,
        "from_task": from_task,
        "to_task": to_task,
        "logical_and": logical_and,
        "eval_op": eval_op,
        "value": value,
        "expression": expression,
    }


# Strategy for a list of constraints (the graph)
constraint_graph = st.lists(constraint_data(), min_size=1, max_size=10)


# --- Helpers ---


def _escape_xml_attr(value: str) -> str:
    """Escape special characters for XML attribute values."""
    value = value.replace("&", "&amp;")
    value = value.replace("<", "&lt;")
    value = value.replace(">", "&gt;")
    value = value.replace('"', "&quot;")
    return value


def _build_constraint_xml(constraints: list[dict]) -> ET.Element:
    """Build a package XML element containing the given precedence constraints.

    Args:
        constraints: List of constraint data dicts.

    Returns:
        An ET.Element representing the package root with constraints.
    """
    # Build XML string manually to have exact control over attributes
    constraint_elems = []
    for c in constraints:
        attrs = [
            f'DTS:refId="{_escape_xml_attr(c["ref_id"])}"',
            f'DTS:DTSID="{_escape_xml_attr(c["dts_id"])}"',
            f'DTS:ObjectName="{_escape_xml_attr(c["object_name"])}"',
            f'DTS:From="{_escape_xml_attr(c["from_task"])}"',
            f'DTS:To="{_escape_xml_attr(c["to_task"])}"',
            f'DTS:LogicalAnd="{c["logical_and"]}"',
            f'DTS:EvalOp="{c["eval_op"]}"',
            f'DTS:Value="{c["value"]}"',
        ]
        if c["expression"]:
            attrs.append(f'DTS:Expression="{_escape_xml_attr(c["expression"])}"')

        constraint_elems.append(f"    <DTS:PrecedenceConstraint {' '.join(attrs)} />")

    constraints_xml = "\n".join(constraint_elems)
    xml_str = (
        f'<DTS:Executable xmlns:DTS="{DTS_NS}">\n'
        f"  <DTS:PrecedenceConstraints>\n"
        f"{constraints_xml}\n"
        f"  </DTS:PrecedenceConstraints>\n"
        f"</DTS:Executable>"
    )
    return ET.fromstring(xml_str)


# --- Property 11: Precedence Constraint Graph Completeness ---
# Feature: pydtsx-parser, Property 11: Precedence Constraint Graph Completeness


class TestPropertyPrecedenceConstraintGraphCompleteness:
    """Property 11: Precedence Constraint Graph Completeness.

    For any package containing precedence constraints, the parser SHALL extract
    each constraint as a directed edge with from-task and to-task references,
    and the complete set of edges SHALL be sufficient to reconstruct the
    original directed execution graph, including the AND/OR logical operator
    for multiple constraints targeting the same task.

    **Validates: Requirements 9.1, 9.2, 9.3, 9.4**
    """

    @given(constraints=constraint_graph)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_all_constraints_extracted_count_matches(self, constraints):
        """All constraints are extracted — count matches input count.

        # Feature: pydtsx-parser, Property 11: Precedence Constraint Graph Completeness
        """
        root = _build_constraint_xml(constraints)
        result = extract_precedence_constraints(root, "test.dtsx")

        assert len(result) == len(constraints), (
            f"Expected {len(constraints)} constraints, got {len(result)}"
        )

    @given(constraints=constraint_graph)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_each_constraint_has_valid_from_and_to(self, constraints):
        """Each extracted constraint has valid from_task and to_task references.

        # Feature: pydtsx-parser, Property 11: Precedence Constraint Graph Completeness
        """
        root = _build_constraint_xml(constraints)
        result = extract_precedence_constraints(root, "test.dtsx")

        for i, extracted in enumerate(result):
            assert "from_task" in extracted, f"Constraint {i} missing 'from_task' key"
            assert "to_task" in extracted, f"Constraint {i} missing 'to_task' key"
            assert (
                extracted["from_task"] is not None and extracted["from_task"] != ""
            ), f"Constraint {i} has empty/null from_task"
            assert extracted["to_task"] is not None and extracted["to_task"] != "", (
                f"Constraint {i} has empty/null to_task"
            )

    @given(constraints=constraint_graph)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_directed_graph_edges_preserved(self, constraints):
        """The set of extracted edges reconstructs the original graph (all from/to pairs preserved).

        # Feature: pydtsx-parser, Property 11: Precedence Constraint Graph Completeness
        """
        root = _build_constraint_xml(constraints)
        result = extract_precedence_constraints(root, "test.dtsx")

        # Build expected edge list (from_task, to_task) in order
        expected_edges = [(c["from_task"], c["to_task"]) for c in constraints]
        actual_edges = [(r["from_task"], r["to_task"]) for r in result]

        assert actual_edges == expected_edges, (
            f"Edge list mismatch.\nExpected: {expected_edges}\nActual: {actual_edges}"
        )

    @given(constraints=constraint_graph)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_logical_and_correctly_represented(self, constraints):
        """LogicalAnd is correctly represented for each constraint.

        # Feature: pydtsx-parser, Property 11: Precedence Constraint Graph Completeness
        """
        root = _build_constraint_xml(constraints)
        result = extract_precedence_constraints(root, "test.dtsx")

        for i, (input_c, extracted) in enumerate(zip(constraints, result)):
            expected_logical_and = input_c["logical_and"].lower() == "true"
            assert extracted["logical_and"] == expected_logical_and, (
                f"Constraint {i}: expected logical_and={expected_logical_and}, "
                f"got {extracted['logical_and']} (input was '{input_c['logical_and']}')"
            )

    @given(constraints=constraint_graph)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_eval_op_and_expression_preserved(self, constraints):
        """EvalOp and expression fields are preserved when present.

        # Feature: pydtsx-parser, Property 11: Precedence Constraint Graph Completeness
        """
        root = _build_constraint_xml(constraints)
        result = extract_precedence_constraints(root, "test.dtsx")

        for i, (input_c, extracted) in enumerate(zip(constraints, result)):
            # EvalOp must match
            assert extracted["eval_op"] == input_c["eval_op"], (
                f"Constraint {i}: expected eval_op='{input_c['eval_op']}', "
                f"got '{extracted['eval_op']}'"
            )

            # Expression must match
            assert extracted["expression"] == input_c["expression"], (
                f"Constraint {i}: expected expression='{input_c['expression']}', "
                f"got '{extracted['expression']}'"
            )

            # Value must be correctly mapped
            expected_value = _CONSTRAINT_VALUE_MAP[input_c["value"]]
            assert extracted["value"] == expected_value, (
                f"Constraint {i}: expected value='{expected_value}', "
                f"got '{extracted['value']}' (raw input='{input_c['value']}')"
            )
