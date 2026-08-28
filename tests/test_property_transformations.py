"""Property-based tests for transformation extraction.

Uses Hypothesis to verify correctness properties of the transformation extractors:
- Property 12: Derived Column Expression Extraction
- Property 13: Sort Component Configuration Extraction
- Property 14: Merge Join Configuration Extraction

**Validates: Requirements 10.1, 10.2, 10.3, 10.4**
"""

import xml.etree.ElementTree as ET

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pydtsx_parser.extractors.sort import extract_sort_details
from pydtsx_parser.extractors.transformations import (
    extract_derived_columns,
    extract_merge_join,
)

# --- Strategies ---

# Safe identifier strings for XML attribute values (no special XML chars)
safe_identifier = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-."),
    min_size=1,
    max_size=30,
)

# Expression text strategy (non-empty, no XML-breaking chars)
expression_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"), whitelist_characters=" _+-*/(),."
    ),
    min_size=1,
    max_size=80,
).filter(lambda s: s.strip() != "")

# Strategy for integer-like attribute values
int_attr_value = st.integers(min_value=0, max_value=99999).map(str)

# Strategy for data type values
data_type_value = st.sampled_from(
    [
        "i2",
        "i4",
        "r4",
        "r8",
        "bool",
        "i8",
        "guid",
        "str",
        "wstr",
        "numeric",
        "dbTimeStamp",
    ]
)

# Strategy for comparison flags
comparison_flags_value = st.sampled_from(["0", "1", "2", "4", "8", "33554432"])

# Number of columns to generate
num_columns = st.integers(min_value=1, max_value=5)


# --- Helpers ---


def _build_derived_column_component(
    new_columns: list[dict],
    overwrite_columns: list[dict],
) -> ET.Element:
    """Build a DerivedColumn component XML element.

    Args:
        new_columns: List of dicts with keys: name, expression, friendly_expression,
            data_type, length, precision, scale, code_page.
        overwrite_columns: List of dicts with keys: cached_name, lineage_id,
            expression, friendly_expression.

    Returns:
        ET.Element representing a DerivedColumn component.
    """
    comp_el = ET.Element(
        "component",
        attrib={
            "refId": "Package\\DerivedColumn",
            "name": "DerivedColumn",
            "componentClassID": "Microsoft.DerivedColumn",
        },
    )

    # Build outputs with new derived columns
    outputs_container = ET.SubElement(comp_el, "outputs")
    output_el = ET.SubElement(
        outputs_container,
        "output",
        attrib={
            "refId": "Package\\DerivedColumn.Outputs[Output]",
            "name": "Derived Column Output",
        },
    )
    if new_columns:
        output_cols_container = ET.SubElement(output_el, "outputColumns")
        for col in new_columns:
            col_el = ET.SubElement(
                output_cols_container,
                "outputColumn",
                attrib={
                    "refId": f"Package\\DerivedColumn.Outputs[Output].Columns[{col['name']}]",
                    "name": col["name"],
                    "dataType": col["data_type"],
                    "length": col["length"],
                    "precision": col["precision"],
                    "scale": col["scale"],
                    "codePage": col["code_page"],
                },
            )
            props_container = ET.SubElement(col_el, "properties")
            expr_prop = ET.SubElement(
                props_container,
                "property",
                attrib={
                    "name": "Expression",
                },
            )
            expr_prop.text = col["expression"]
            friendly_prop = ET.SubElement(
                props_container,
                "property",
                attrib={
                    "name": "FriendlyExpression",
                },
            )
            friendly_prop.text = col["friendly_expression"]

    # Add an error output (should be skipped)
    error_output = ET.SubElement(
        outputs_container,
        "output",
        attrib={
            "refId": "Package\\DerivedColumn.Outputs[ErrorOutput]",
            "name": "Error Output",
            "isErrorOut": "true",
        },
    )

    # Build inputs with overwrite columns
    inputs_container = ET.SubElement(comp_el, "inputs")
    input_el = ET.SubElement(
        inputs_container,
        "input",
        attrib={
            "refId": "Package\\DerivedColumn.Inputs[Input]",
            "name": "Derived Column Input",
        },
    )
    if overwrite_columns:
        input_cols_container = ET.SubElement(input_el, "inputColumns")
        for col in overwrite_columns:
            col_el = ET.SubElement(
                input_cols_container,
                "inputColumn",
                attrib={
                    "refId": f"Package\\DerivedColumn.Inputs[Input].Columns[{col['cached_name']}]",
                    "cachedName": col["cached_name"],
                    "lineageId": col["lineage_id"],
                    "usageType": "readWrite",
                },
            )
            props_container = ET.SubElement(col_el, "properties")
            expr_prop = ET.SubElement(
                props_container,
                "property",
                attrib={
                    "name": "Expression",
                },
            )
            expr_prop.text = col["expression"]
            friendly_prop = ET.SubElement(
                props_container,
                "property",
                attrib={
                    "name": "FriendlyExpression",
                },
            )
            friendly_prop.text = col["friendly_expression"]

    return comp_el


def _build_sort_component(
    sort_columns: list[dict],
    eliminate_duplicates: bool,
    passthrough_columns: list[str] | None = None,
) -> ET.Element:
    """Build a Sort component XML element.

    Args:
        sort_columns: List of dicts with keys: name, sort_key_position (signed int),
            comparison_flags.
        eliminate_duplicates: Whether EliminateDuplicates is set.
        passthrough_columns: Optional list of column names with SortKeyPosition=0.

    Returns:
        ET.Element representing a Sort component.
    """
    comp_el = ET.Element(
        "component",
        attrib={
            "refId": "Package\\Sort",
            "name": "Sort",
            "componentClassID": "Microsoft.Sort",
        },
    )

    # Add EliminateDuplicates property
    props_container = ET.SubElement(comp_el, "properties")
    elim_prop = ET.SubElement(
        props_container,
        "property",
        attrib={
            "name": "EliminateDuplicates",
        },
    )
    elim_prop.text = "1" if eliminate_duplicates else "0"

    # Build outputs
    outputs_container = ET.SubElement(comp_el, "outputs")
    output_el = ET.SubElement(
        outputs_container,
        "output",
        attrib={
            "refId": "Package\\Sort.Outputs[Output]",
            "name": "Sort Output",
        },
    )
    output_cols_container = ET.SubElement(output_el, "outputColumns")

    # Add sort key columns
    for col in sort_columns:
        col_el = ET.SubElement(
            output_cols_container,
            "outputColumn",
            attrib={
                "refId": f"Package\\Sort.Outputs[Output].Columns[{col['name']}]",
                "name": col["name"],
                "dataType": "wstr",
                "length": "50",
            },
        )
        col_props = ET.SubElement(col_el, "properties")
        skp_prop = ET.SubElement(
            col_props, "property", attrib={"name": "SortKeyPosition"}
        )
        skp_prop.text = str(col["sort_key_position"])
        cf_prop = ET.SubElement(
            col_props, "property", attrib={"name": "ComparisonFlags"}
        )
        cf_prop.text = col["comparison_flags"]

    # Add passthrough columns (SortKeyPosition=0)
    if passthrough_columns:
        for pt_name in passthrough_columns:
            col_el = ET.SubElement(
                output_cols_container,
                "outputColumn",
                attrib={
                    "refId": f"Package\\Sort.Outputs[Output].Columns[{pt_name}]",
                    "name": pt_name,
                    "dataType": "wstr",
                    "length": "50",
                },
            )
            col_props = ET.SubElement(col_el, "properties")
            skp_prop = ET.SubElement(
                col_props, "property", attrib={"name": "SortKeyPosition"}
            )
            skp_prop.text = "0"
            cf_prop = ET.SubElement(
                col_props, "property", attrib={"name": "ComparisonFlags"}
            )
            cf_prop.text = "0"

    # Add error output (should be skipped)
    error_output = ET.SubElement(
        outputs_container,
        "output",
        attrib={
            "refId": "Package\\Sort.Outputs[ErrorOutput]",
            "name": "Sort Error Output",
            "isErrorOut": "true",
        },
    )

    return comp_el


def _build_merge_join_component(
    join_type_code: str,
    treat_nulls_as_equal: bool,
    left_keys: list[dict],
    right_keys: list[dict],
    output_columns: list[dict],
) -> ET.Element:
    """Build a MergeJoin component XML element.

    Args:
        join_type_code: Numeric join type ("0", "1", "2", or other).
        treat_nulls_as_equal: Whether TreatNullsAsEqual is set.
        left_keys: List of dicts with keys: name, sort_key_position (positive int).
        right_keys: List of dicts with keys: name, sort_key_position (positive int).
        output_columns: List of dicts with keys: name, data_type, length, precision,
            scale, code_page, lineage_id.

    Returns:
        ET.Element representing a MergeJoin component.
    """
    comp_el = ET.Element(
        "component",
        attrib={
            "refId": "Package\\MergeJoin",
            "name": "MergeJoin",
            "componentClassID": "Microsoft.MergeJoin",
        },
    )

    # Component properties
    props_container = ET.SubElement(comp_el, "properties")
    jt_prop = ET.SubElement(props_container, "property", attrib={"name": "JoinType"})
    jt_prop.text = join_type_code
    tne_prop = ET.SubElement(
        props_container, "property", attrib={"name": "TreatNullsAsEqual"}
    )
    tne_prop.text = "true" if treat_nulls_as_equal else "false"

    # Build inputs (left=index 0, right=index 1)
    inputs_container = ET.SubElement(comp_el, "inputs")

    # Left input
    left_input = ET.SubElement(
        inputs_container,
        "input",
        attrib={
            "refId": "Package\\MergeJoin.Inputs[Left]",
            "name": "Merge Join Left Input",
        },
    )
    if left_keys:
        left_cols_container = ET.SubElement(left_input, "inputColumns")
        for col in left_keys:
            ET.SubElement(
                left_cols_container,
                "inputColumn",
                attrib={
                    "refId": f"Package\\MergeJoin.Inputs[Left].Columns[{col['name']}]",
                    "cachedName": col["name"],
                    "cachedSortKeyPosition": str(col["sort_key_position"]),
                    "lineageId": str(col.get("lineage_id", "100")),
                },
            )

    # Right input
    right_input = ET.SubElement(
        inputs_container,
        "input",
        attrib={
            "refId": "Package\\MergeJoin.Inputs[Right]",
            "name": "Merge Join Right Input",
        },
    )
    if right_keys:
        right_cols_container = ET.SubElement(right_input, "inputColumns")
        for col in right_keys:
            ET.SubElement(
                right_cols_container,
                "inputColumn",
                attrib={
                    "refId": f"Package\\MergeJoin.Inputs[Right].Columns[{col['name']}]",
                    "cachedName": col["name"],
                    "cachedSortKeyPosition": str(col["sort_key_position"]),
                    "lineageId": str(col.get("lineage_id", "200")),
                },
            )

    # Build outputs
    outputs_container = ET.SubElement(comp_el, "outputs")
    output_el = ET.SubElement(
        outputs_container,
        "output",
        attrib={
            "refId": "Package\\MergeJoin.Outputs[Output]",
            "name": "Merge Join Output",
        },
    )
    if output_columns:
        output_cols_container = ET.SubElement(output_el, "outputColumns")
        for col in output_columns:
            ET.SubElement(
                output_cols_container,
                "outputColumn",
                attrib={
                    "refId": f"Package\\MergeJoin.Outputs[Output].Columns[{col['name']}]",
                    "name": col["name"],
                    "dataType": col["data_type"],
                    "length": col["length"],
                    "precision": col["precision"],
                    "scale": col["scale"],
                    "codePage": col["code_page"],
                    "lineageId": col["lineage_id"],
                },
            )

    # Add error output (should be skipped)
    error_output = ET.SubElement(
        outputs_container,
        "output",
        attrib={
            "refId": "Package\\MergeJoin.Outputs[ErrorOutput]",
            "name": "Merge Join Error Output",
            "isErrorOut": "true",
        },
    )

    return comp_el


# --- Property 12: Derived Column Expression Extraction ---
# Feature: pydtsx-parser, Property 12: Derived Column Expression Extraction


class TestPropertyDerivedColumnExpressionExtraction:
    """Property 12: Derived Column Expression Extraction.

    For any DerivedColumn transformation component, the parser SHALL extract
    every derived column definition including its expression text and friendly
    expression text, and SHALL correctly flag columns as overwrites (with original
    lineageId reference) when the input column has usageType="readWrite".

    **Validates: Requirements 10.1, 10.2**
    """

    @given(
        num_new=st.integers(min_value=0, max_value=4),
        num_overwrites=st.integers(min_value=0, max_value=3),
        data=st.data(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_all_derived_columns_extracted(self, num_new, num_overwrites, data):
        """Every generated derived column (new or overwrite) is extracted."""
        # Feature: pydtsx-parser, Property 12: Derived Column Expression Extraction

        # Generate new column definitions
        new_columns = []
        for i in range(num_new):
            name = data.draw(safe_identifier, label=f"new_col_name_{i}")
            expr = data.draw(expression_text, label=f"new_col_expr_{i}")
            friendly_expr = data.draw(expression_text, label=f"new_col_friendly_{i}")
            dt = data.draw(data_type_value, label=f"new_col_dt_{i}")
            length = data.draw(int_attr_value, label=f"new_col_len_{i}")
            precision = data.draw(int_attr_value, label=f"new_col_prec_{i}")
            scale = data.draw(int_attr_value, label=f"new_col_scale_{i}")
            code_page = data.draw(int_attr_value, label=f"new_col_cp_{i}")

            new_columns.append(
                {
                    "name": name,
                    "expression": expr,
                    "friendly_expression": friendly_expr,
                    "data_type": dt,
                    "length": length,
                    "precision": precision,
                    "scale": scale,
                    "code_page": code_page,
                }
            )

        # Generate overwrite column definitions
        overwrite_columns = []
        for i in range(num_overwrites):
            cached_name = data.draw(safe_identifier, label=f"ow_col_name_{i}")
            lineage_id = data.draw(
                st.integers(min_value=1, max_value=99999).map(str),
                label=f"ow_col_lid_{i}",
            )
            expr = data.draw(expression_text, label=f"ow_col_expr_{i}")
            friendly_expr = data.draw(expression_text, label=f"ow_col_friendly_{i}")

            overwrite_columns.append(
                {
                    "cached_name": cached_name,
                    "lineage_id": lineage_id,
                    "expression": expr,
                    "friendly_expression": friendly_expr,
                }
            )

        comp_el = _build_derived_column_component(new_columns, overwrite_columns)
        result = extract_derived_columns(comp_el)

        # Total derived columns must equal new + overwrite
        assert len(result["derived_columns"]) == num_new + num_overwrites

    @given(
        num_new=st.integers(min_value=1, max_value=4),
        data=st.data(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_new_columns_flagged_not_overwrite(self, num_new, data):
        """New derived columns have is_overwrite=False."""
        # Feature: pydtsx-parser, Property 12: Derived Column Expression Extraction

        new_columns = []
        for i in range(num_new):
            new_columns.append(
                {
                    "name": data.draw(safe_identifier, label=f"name_{i}"),
                    "expression": data.draw(expression_text, label=f"expr_{i}"),
                    "friendly_expression": data.draw(
                        expression_text, label=f"friendly_{i}"
                    ),
                    "data_type": data.draw(data_type_value, label=f"dt_{i}"),
                    "length": data.draw(int_attr_value, label=f"len_{i}"),
                    "precision": data.draw(int_attr_value, label=f"prec_{i}"),
                    "scale": data.draw(int_attr_value, label=f"scale_{i}"),
                    "code_page": data.draw(int_attr_value, label=f"cp_{i}"),
                }
            )

        comp_el = _build_derived_column_component(new_columns, [])
        result = extract_derived_columns(comp_el)

        for col_def in result["derived_columns"]:
            assert col_def["is_overwrite"] is False

    @given(
        num_overwrites=st.integers(min_value=1, max_value=4),
        data=st.data(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_overwrite_columns_flagged_correctly(self, num_overwrites, data):
        """Overwrite columns have is_overwrite=True and original_lineage_id set."""
        # Feature: pydtsx-parser, Property 12: Derived Column Expression Extraction

        overwrite_columns = []
        for i in range(num_overwrites):
            lineage_id = data.draw(
                st.integers(min_value=1, max_value=99999).map(str),
                label=f"lid_{i}",
            )
            overwrite_columns.append(
                {
                    "cached_name": data.draw(safe_identifier, label=f"name_{i}"),
                    "lineage_id": lineage_id,
                    "expression": data.draw(expression_text, label=f"expr_{i}"),
                    "friendly_expression": data.draw(
                        expression_text, label=f"friendly_{i}"
                    ),
                }
            )

        comp_el = _build_derived_column_component([], overwrite_columns)
        result = extract_derived_columns(comp_el)

        for i, col_def in enumerate(result["derived_columns"]):
            assert col_def["is_overwrite"] is True
            assert col_def["original_lineage_id"] == overwrite_columns[i]["lineage_id"]

    @given(
        data=st.data(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_expression_text_preserved_exactly(self, data):
        """Expression and FriendlyExpression text values are preserved exactly."""
        # Feature: pydtsx-parser, Property 12: Derived Column Expression Extraction

        expr = data.draw(expression_text, label="expression")
        friendly_expr = data.draw(expression_text, label="friendly_expression")

        new_columns = [
            {
                "name": "TestCol",
                "expression": expr,
                "friendly_expression": friendly_expr,
                "data_type": "wstr",
                "length": "50",
                "precision": "0",
                "scale": "0",
                "code_page": "0",
            }
        ]

        comp_el = _build_derived_column_component(new_columns, [])
        result = extract_derived_columns(comp_el)

        assert len(result["derived_columns"]) == 1
        assert result["derived_columns"][0]["expression"] == expr
        assert result["derived_columns"][0]["friendly_expression"] == friendly_expr


# --- Property 13: Sort Component Configuration Extraction ---
# Feature: pydtsx-parser, Property 13: Sort Component Configuration Extraction


class TestPropertySortComponentConfigurationExtraction:
    """Property 13: Sort Component Configuration Extraction.

    For any Sort transformation component, the parser SHALL extract all sort
    columns with their absolute sort key position, sort order (ascending for
    positive sortKeyPosition, descending for negative), comparison flags, and
    the EliminateDuplicates property value.

    **Validates: Requirements 10.3**
    """

    @given(
        num_cols=st.integers(min_value=1, max_value=5),
        eliminate_duplicates=st.booleans(),
        data=st.data(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_all_sort_columns_extracted(self, num_cols, eliminate_duplicates, data):
        """All sort columns with non-zero SortKeyPosition are extracted."""
        # Feature: pydtsx-parser, Property 13: Sort Component Configuration Extraction

        sort_columns = []
        used_positions = set()
        for i in range(num_cols):
            name = data.draw(safe_identifier, label=f"sort_col_name_{i}")
            # Generate non-zero signed position, ensure unique absolute values
            position = data.draw(
                st.integers(min_value=1, max_value=20).filter(
                    lambda p: p not in used_positions
                ),
                label=f"sort_col_pos_{i}",
            )
            used_positions.add(position)
            sign = data.draw(st.sampled_from([1, -1]), label=f"sort_col_sign_{i}")
            flags = data.draw(comparison_flags_value, label=f"sort_col_flags_{i}")

            sort_columns.append(
                {
                    "name": name,
                    "sort_key_position": sign * position,
                    "comparison_flags": flags,
                }
            )

        # Add some passthrough columns that should NOT be extracted
        passthrough = [f"passthrough_{i}" for i in range(2)]

        comp_el = _build_sort_component(sort_columns, eliminate_duplicates, passthrough)
        result = extract_sort_details(comp_el)

        # Only sort key columns should be extracted (not passthrough)
        assert len(result["sort_columns"]) == num_cols

    @given(
        data=st.data(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_sort_order_correctly_determined(self, data):
        """Positive sortKeyPosition=ascending, negative=descending."""
        # Feature: pydtsx-parser, Property 13: Sort Component Configuration Extraction

        position = data.draw(st.integers(min_value=1, max_value=10), label="position")
        sign = data.draw(st.sampled_from([1, -1]), label="sign")
        name = data.draw(safe_identifier, label="name")

        sort_columns = [
            {
                "name": name,
                "sort_key_position": sign * position,
                "comparison_flags": "0",
            }
        ]

        comp_el = _build_sort_component(sort_columns, False)
        result = extract_sort_details(comp_el)

        assert len(result["sort_columns"]) == 1
        extracted = result["sort_columns"][0]

        expected_order = "ascending" if sign > 0 else "descending"
        assert extracted["sort_order"] == expected_order
        assert extracted["sort_key_position"] == position  # absolute value

    @given(eliminate_duplicates=st.booleans())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_eliminate_duplicates_correctly_extracted(self, eliminate_duplicates):
        """EliminateDuplicates property is correctly extracted."""
        # Feature: pydtsx-parser, Property 13: Sort Component Configuration Extraction

        sort_columns = [
            {
                "name": "Col1",
                "sort_key_position": 1,
                "comparison_flags": "0",
            }
        ]

        comp_el = _build_sort_component(sort_columns, eliminate_duplicates)
        result = extract_sort_details(comp_el)

        assert result["eliminate_duplicates"] is eliminate_duplicates

    @given(
        data=st.data(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_sort_columns_ordered_by_position(self, data):
        """Columns are sorted by sort_key_position in the output."""
        # Feature: pydtsx-parser, Property 13: Sort Component Configuration Extraction

        num_cols = data.draw(st.integers(min_value=2, max_value=5), label="num_cols")
        positions = data.draw(
            st.lists(
                st.integers(min_value=1, max_value=20),
                min_size=num_cols,
                max_size=num_cols,
                unique=True,
            ),
            label="positions",
        )

        sort_columns = []
        for i, pos in enumerate(positions):
            sign = data.draw(st.sampled_from([1, -1]), label=f"sign_{i}")
            sort_columns.append(
                {
                    "name": f"Col_{i}",
                    "sort_key_position": sign * pos,
                    "comparison_flags": "0",
                }
            )

        comp_el = _build_sort_component(sort_columns, False)
        result = extract_sort_details(comp_el)

        # Verify output is ordered by sort_key_position (ascending)
        extracted_positions = [c["sort_key_position"] for c in result["sort_columns"]]
        assert extracted_positions == sorted(extracted_positions)


# --- Property 14: Merge Join Configuration Extraction ---
# Feature: pydtsx-parser, Property 14: Merge Join Configuration Extraction


class TestPropertyMergeJoinConfigurationExtraction:
    """Property 14: Merge Join Configuration Extraction.

    For any MergeJoin transformation component, the parser SHALL extract the
    join type as a human-readable name (translating 0→FULL, 1→LEFT, 2→INNER from
    the numeric JoinType property), the join key column pairs, and the
    TreatNullsAsEqual property value.

    **Validates: Requirements 10.4**
    """

    @given(join_type_code=st.sampled_from(["0", "1", "2"]))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_known_join_type_translation(self, join_type_code):
        """JoinType numeric values (0,1,2) correctly translate to FULL, LEFT, INNER."""
        # Feature: pydtsx-parser, Property 14: Merge Join Configuration Extraction

        expected_map = {"0": "FULL", "1": "LEFT", "2": "INNER"}

        comp_el = _build_merge_join_component(
            join_type_code=join_type_code,
            treat_nulls_as_equal=False,
            left_keys=[{"name": "Key1", "sort_key_position": 1}],
            right_keys=[{"name": "Key1", "sort_key_position": 1}],
            output_columns=[],
        )
        result = extract_merge_join(comp_el)

        assert result["join_type"] == expected_map[join_type_code]

    @given(
        unknown_code=st.text(
            alphabet=st.characters(whitelist_categories=("N",)),
            min_size=1,
            max_size=5,
        ).filter(lambda s: s.strip() not in ("0", "1", "2"))
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_unknown_join_type_returns_unknown(self, unknown_code):
        """Unknown JoinType returns 'UNKNOWN'."""
        # Feature: pydtsx-parser, Property 14: Merge Join Configuration Extraction

        comp_el = _build_merge_join_component(
            join_type_code=unknown_code,
            treat_nulls_as_equal=False,
            left_keys=[{"name": "Key1", "sort_key_position": 1}],
            right_keys=[{"name": "Key1", "sort_key_position": 1}],
            output_columns=[],
        )
        result = extract_merge_join(comp_el)

        assert result["join_type"] == "UNKNOWN"

    @given(treat_nulls=st.booleans())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_treat_nulls_as_equal_correctly_extracted(self, treat_nulls):
        """TreatNullsAsEqual is correctly extracted."""
        # Feature: pydtsx-parser, Property 14: Merge Join Configuration Extraction

        comp_el = _build_merge_join_component(
            join_type_code="2",
            treat_nulls_as_equal=treat_nulls,
            left_keys=[{"name": "Key1", "sort_key_position": 1}],
            right_keys=[{"name": "Key1", "sort_key_position": 1}],
            output_columns=[],
        )
        result = extract_merge_join(comp_el)

        assert result["treat_nulls_as_equal"] is treat_nulls

    @given(
        num_keys=st.integers(min_value=1, max_value=4),
        data=st.data(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_join_key_pairs_matched_by_sort_key_position(self, num_keys, data):
        """Join key pairs are correctly matched by cachedSortKeyPosition."""
        # Feature: pydtsx-parser, Property 14: Merge Join Configuration Extraction

        positions = data.draw(
            st.lists(
                st.integers(min_value=1, max_value=10),
                min_size=num_keys,
                max_size=num_keys,
                unique=True,
            ),
            label="positions",
        )

        left_keys = []
        right_keys = []
        for i, pos in enumerate(positions):
            left_name = data.draw(safe_identifier, label=f"left_name_{i}")
            right_name = data.draw(safe_identifier, label=f"right_name_{i}")
            left_keys.append({"name": left_name, "sort_key_position": pos})
            right_keys.append({"name": right_name, "sort_key_position": pos})

        comp_el = _build_merge_join_component(
            join_type_code="2",
            treat_nulls_as_equal=False,
            left_keys=left_keys,
            right_keys=right_keys,
            output_columns=[],
        )
        result = extract_merge_join(comp_el)

        # All key pairs should be extracted
        assert len(result["join_keys"]) == num_keys

        # Each key pair should match by sort_key_position
        for join_key in result["join_keys"]:
            pos = join_key["sort_key_position"]
            # Find the matching left and right keys
            left_match = next(k for k in left_keys if k["sort_key_position"] == pos)
            right_match = next(k for k in right_keys if k["sort_key_position"] == pos)
            assert join_key["left_column"] == left_match["name"]
            assert join_key["right_column"] == right_match["name"]

    @given(
        num_output_cols=st.integers(min_value=1, max_value=4),
        data=st.data(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_output_columns_extracted_from_non_error_outputs(
        self, num_output_cols, data
    ):
        """Output columns are extracted from non-error outputs."""
        # Feature: pydtsx-parser, Property 14: Merge Join Configuration Extraction

        output_columns = []
        for i in range(num_output_cols):
            output_columns.append(
                {
                    "name": data.draw(safe_identifier, label=f"out_name_{i}"),
                    "data_type": data.draw(data_type_value, label=f"out_dt_{i}"),
                    "length": data.draw(int_attr_value, label=f"out_len_{i}"),
                    "precision": data.draw(int_attr_value, label=f"out_prec_{i}"),
                    "scale": data.draw(int_attr_value, label=f"out_scale_{i}"),
                    "code_page": data.draw(int_attr_value, label=f"out_cp_{i}"),
                    "lineage_id": data.draw(int_attr_value, label=f"out_lid_{i}"),
                }
            )

        comp_el = _build_merge_join_component(
            join_type_code="2",
            treat_nulls_as_equal=False,
            left_keys=[{"name": "Key1", "sort_key_position": 1}],
            right_keys=[{"name": "Key1", "sort_key_position": 1}],
            output_columns=output_columns,
        )
        result = extract_merge_join(comp_el)

        # Output columns from non-error output must be extracted
        assert len(result["output_columns"]) == num_output_cols

        for i, col in enumerate(result["output_columns"]):
            assert col["name"] == output_columns[i]["name"]
            assert col["data_type"] == output_columns[i]["data_type"]
            assert col["length"] == output_columns[i]["length"]
            assert col["precision"] == output_columns[i]["precision"]
            assert col["scale"] == output_columns[i]["scale"]
            assert col["code_page"] == output_columns[i]["code_page"]
            assert col["lineage_id"] == output_columns[i]["lineage_id"]
