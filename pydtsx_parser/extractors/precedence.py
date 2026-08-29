"""Precedence constraint extraction from DTS:PrecedenceConstraints elements.

Extracts control flow ordering information from SSIS packages. Each
precedence constraint represents a directed edge in the task execution
graph, specifying which task must complete before another can begin,
along with optional conditional evaluation logic.

Handles three cases:
- Normal constraints with all required attributes → extracted as edge dicts
- Empty or missing DTS:PrecedenceConstraints → returns empty list (not an error)
- Malformed constraints missing DTS:From or DTS:To → raises ExtractionError
"""

import xml.etree.ElementTree as ET

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.errors import ExtractionError

_DTS_NS = NAMESPACES["DTS"]

# Constraint value mapping: numeric codes to human-readable names
_CONSTRAINT_VALUE_MAP = {
    "0": "Success",
    "1": "Failure",
    "2": "Completion",
}


def extract_precedence_constraints(
    parent_element: ET.Element, file_path: str = ""
) -> list[dict]:
    """Extract all precedence constraints from a parent element.

    Looks for a DTS:PrecedenceConstraints child element and extracts each
    DTS:PrecedenceConstraint within it as a directed edge in the control
    flow graph.

    Args:
        parent_element: The XML element containing a DTS:PrecedenceConstraints
            child (typically the package root element).
        file_path: Source file path for error reporting.

    Returns:
        List of constraint dicts. Returns empty list if no
        DTS:PrecedenceConstraints element exists or it is empty.

    Raises:
        ExtractionError: If a constraint element is missing required
            DTS:From or DTS:To attributes.
    """
    constraints_container = parent_element.find(f"{{{_DTS_NS}}}PrecedenceConstraints")
    if constraints_container is None:
        return []

    results = []
    for constraint_elem in constraints_container.findall(
        f"{{{_DTS_NS}}}PrecedenceConstraint"
    ):
        constraint = _extract_single_constraint(constraint_elem, file_path)
        results.append(constraint)

    return results


def _extract_single_constraint(constraint_elem: ET.Element, file_path: str) -> dict:
    """Extract a single DTS:PrecedenceConstraint element into a dict.

    Extracts required attributes (refId, DTSID, ObjectName, From, To),
    the LogicalAnd flag, and optional expression evaluation fields
    (EvalOp, Expression, Value).

    Args:
        constraint_elem: A DTS:PrecedenceConstraint XML element.
        file_path: Source file path for error reporting.

    Returns:
        Dictionary with constraint properties representing a directed edge.

    Raises:
        ExtractionError: If DTS:From or DTS:To attributes are missing.
    """
    # Extract required from/to references - raise error if missing
    from_task = constraint_elem.get(f"{{{_DTS_NS}}}From")
    to_task = constraint_elem.get(f"{{{_DTS_NS}}}To")

    if from_task is None or to_task is None:
        missing = []
        if from_task is None:
            missing.append("DTS:From")
        if to_task is None:
            missing.append("DTS:To")
        raise ExtractionError(
            file_path,
            f"Precedence constraint is missing required attribute(s): {', '.join(missing)}",
        )

    # Extract common attributes
    ref_id = constraint_elem.get(f"{{{_DTS_NS}}}refId", "")
    dts_id = constraint_elem.get(f"{{{_DTS_NS}}}DTSID", "")
    object_name = constraint_elem.get(f"{{{_DTS_NS}}}ObjectName", "")

    # LogicalAnd: convert "True"/"False" string to Python bool, default True
    logical_and_str = constraint_elem.get(f"{{{_DTS_NS}}}LogicalAnd", "True")
    logical_and = logical_and_str.lower() == "true"

    # EvalOp determines the evaluation mode
    # Default is "Constraint" (simple success/failure/completion check)
    eval_op = constraint_elem.get(f"{{{_DTS_NS}}}EvalOp", "Constraint")

    # Expression text (only meaningful for expression-based EvalOp values)
    expression = constraint_elem.get(f"{{{_DTS_NS}}}Expression", "")

    # Constraint value: numeric code or already human-readable
    raw_value = constraint_elem.get(f"{{{_DTS_NS}}}Value", "0")
    value = _CONSTRAINT_VALUE_MAP.get(raw_value, raw_value)

    return {
        "ref_id": ref_id,
        "dts_id": dts_id,
        "object_name": object_name,
        "from_task": from_task,
        "to_task": to_task,
        "eval_op": eval_op,
        "expression": expression,
        "value": value,
        "logical_and": logical_and,
    }
