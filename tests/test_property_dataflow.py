"""Property-based tests for data flow extraction.

Uses Hypothesis to verify correctness properties of the data flow extractors:
- Property 2: Column Metadata Completeness
- Property 3: Component Classification Correctness
- Property 4: Lineage ID Preservation
- Property 15: Topological Sort Validity

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 11.2**
"""

import xml.etree.ElementTree as ET

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from pydtsx_parser.constants import COMPONENT_CLASSIFICATION
from pydtsx_parser.extractors.columns import (
    extract_external_metadata,
    extract_input_columns,
    extract_output_columns,
)
from pydtsx_parser.extractors.components import classify_component, extract_component
from pydtsx_parser.extractors.paths import compute_topological_order

# --- Strategies ---

# Safe identifier strings for XML attribute values (no special XML chars)
safe_identifier = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-."),
    min_size=1,
    max_size=30,
)

# Strategy for integer-like attribute values (lineageId, length, precision, scale, codePage)
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
        "numericWithPrecision",
    ]
)

# Strategy for error/truncation row dispositions
disposition_value = st.sampled_from(
    [
        "NotUsed",
        "IgnoreFailure",
        "FailComponent",
        "RedirectRow",
    ]
)

# Number of columns to generate per element
num_columns = st.integers(min_value=0, max_value=5)

# Known component class IDs from the registry
known_class_ids = list(COMPONENT_CLASSIFICATION.keys())

# Strategy for component class IDs (mix of known and unknown)
component_class_id_strategy = st.one_of(
    st.sampled_from(known_class_ids),
    st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N"), whitelist_characters="_."
        ),
        min_size=5,
        max_size=40,
    ),
)

# Strategy for unique component names
component_name = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
    min_size=1,
    max_size=20,
)


# --- Helpers ---


def _build_input_element(columns_data: list[dict]) -> ET.Element:
    """Build an <input> XML element with inputColumns.

    Args:
        columns_data: List of dicts with keys matching inputColumn attributes.

    Returns:
        An ET.Element representing the <input>.
    """
    input_el = ET.Element("input", attrib={"refId": "TestInput", "name": "TestInput"})
    if columns_data:
        columns_container = ET.SubElement(input_el, "inputColumns")
        for col in columns_data:
            ET.SubElement(columns_container, "inputColumn", attrib=col)
    return input_el


def _build_output_element(columns_data: list[dict]) -> ET.Element:
    """Build an <output> XML element with outputColumns.

    Args:
        columns_data: List of dicts with keys matching outputColumn attributes.

    Returns:
        An ET.Element representing the <output>.
    """
    output_el = ET.Element(
        "output", attrib={"refId": "TestOutput", "name": "TestOutput"}
    )
    if columns_data:
        columns_container = ET.SubElement(output_el, "outputColumns")
        for col in columns_data:
            ET.SubElement(columns_container, "outputColumn", attrib=col)
    return output_el


def _build_external_metadata_element(columns_data: list[dict]) -> ET.Element:
    """Build an <input> or <output> element with externalMetadataColumns.

    Args:
        columns_data: List of dicts with keys matching externalMetadataColumn attributes.

    Returns:
        An ET.Element representing the <input> with external metadata.
    """
    parent_el = ET.Element(
        "input", attrib={"refId": "TestParent", "name": "TestParent"}
    )
    if columns_data:
        columns_container = ET.SubElement(parent_el, "externalMetadataColumns")
        for col in columns_data:
            ET.SubElement(columns_container, "externalMetadataColumn", attrib=col)
    return parent_el


def _build_component_element(
    ref_id: str,
    name: str,
    class_id: str,
    input_columns: list[dict] | None = None,
    output_columns: list[dict] | None = None,
    num_inputs: int = 1,
    num_outputs: int = 1,
) -> ET.Element:
    """Build a <component> XML element for testing.

    Args:
        ref_id: Component refId attribute.
        name: Component name attribute.
        class_id: componentClassID attribute.
        input_columns: Optional list of inputColumn attribute dicts.
        output_columns: Optional list of outputColumn attribute dicts.
        num_inputs: Number of input elements to create.
        num_outputs: Number of output elements to create.

    Returns:
        An ET.Element representing the <component>.
    """
    comp_el = ET.Element(
        "component",
        attrib={
            "refId": ref_id,
            "name": name,
            "componentClassID": class_id,
            "contactInfo": "Test Contact",
            "version": "1",
            "usesDispositions": "true",
        },
    )

    # Add inputs
    if num_inputs > 0:
        inputs_container = ET.SubElement(comp_el, "inputs")
        for i in range(num_inputs):
            input_el = ET.SubElement(
                inputs_container,
                "input",
                attrib={
                    "refId": f"{ref_id}.Inputs[Input{i}]",
                    "name": f"Input{i}",
                },
            )
            if input_columns and i == 0:
                columns_container = ET.SubElement(input_el, "inputColumns")
                for col in input_columns:
                    ET.SubElement(columns_container, "inputColumn", attrib=col)

    # Add outputs
    if num_outputs > 0:
        outputs_container = ET.SubElement(comp_el, "outputs")
        for i in range(num_outputs):
            output_el = ET.SubElement(
                outputs_container,
                "output",
                attrib={
                    "refId": f"{ref_id}.Outputs[Output{i}]",
                    "name": f"Output{i}",
                },
            )
            if output_columns and i == 0:
                columns_container = ET.SubElement(output_el, "outputColumns")
                for col in output_columns:
                    ET.SubElement(columns_container, "outputColumn", attrib=col)

    return comp_el


# --- Property 2: Column Metadata Completeness ---
# Feature: pydtsx-parser, Property 2: Column Metadata Completeness


class TestPropertyColumnMetadataCompleteness:
    """Property 2: Column Metadata Completeness.

    For any data flow component containing input columns, output columns, or
    external metadata columns, the parser SHALL extract every column with all
    specified metadata fields, and the count of extracted columns SHALL equal
    the count of column elements in the source XML.

    **Validates: Requirements 2.1, 2.2, 2.3**
    """

    @given(
        num_cols=num_columns,
        ref_ids=st.lists(safe_identifier, min_size=5, max_size=5),
        cached_names=st.lists(safe_identifier, min_size=5, max_size=5),
        data_types=st.lists(data_type_value, min_size=5, max_size=5),
        lengths=st.lists(int_attr_value, min_size=5, max_size=5),
        precisions=st.lists(int_attr_value, min_size=5, max_size=5),
        scales=st.lists(int_attr_value, min_size=5, max_size=5),
        codepages=st.lists(int_attr_value, min_size=5, max_size=5),
        lineage_ids=st.lists(int_attr_value, min_size=5, max_size=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_input_columns_count_and_fields_match(
        self,
        num_cols,
        ref_ids,
        cached_names,
        data_types,
        lengths,
        precisions,
        scales,
        codepages,
        lineage_ids,
    ):
        """All input columns are extracted with all metadata fields."""
        # Feature: pydtsx-parser, Property 2: Column Metadata Completeness

        columns_data = []
        for i in range(num_cols):
            columns_data.append(
                {
                    "refId": ref_ids[i],
                    "cachedName": cached_names[i],
                    "cachedDataType": data_types[i],
                    "cachedLength": lengths[i],
                    "cachedPrecision": precisions[i],
                    "cachedScale": scales[i],
                    "cachedCodepage": codepages[i],
                    "lineageId": lineage_ids[i],
                    "externalMetadataColumnId": str(i),
                }
            )

        input_el = _build_input_element(columns_data)
        result = extract_input_columns(input_el)

        # Count must match
        assert len(result) == num_cols

        # Each column must have all expected fields
        for i, col in enumerate(result):
            assert col["ref_id"] == ref_ids[i]
            assert col["cached_name"] == cached_names[i]
            assert col["cached_data_type"] == data_types[i]
            assert col["cached_length"] == lengths[i]
            assert col["cached_precision"] == precisions[i]
            assert col["cached_scale"] == scales[i]
            assert col["cached_codepage"] == codepages[i]
            assert col["lineage_id"] == lineage_ids[i]
            assert col["external_metadata_column_id"] == str(i)

    @given(
        num_cols=num_columns,
        ref_ids=st.lists(safe_identifier, min_size=5, max_size=5),
        names=st.lists(safe_identifier, min_size=5, max_size=5),
        data_types=st.lists(data_type_value, min_size=5, max_size=5),
        lengths=st.lists(int_attr_value, min_size=5, max_size=5),
        precisions=st.lists(int_attr_value, min_size=5, max_size=5),
        scales=st.lists(int_attr_value, min_size=5, max_size=5),
        codepages=st.lists(int_attr_value, min_size=5, max_size=5),
        lineage_ids=st.lists(int_attr_value, min_size=5, max_size=5),
        dispositions=st.lists(disposition_value, min_size=5, max_size=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_output_columns_count_and_fields_match(
        self,
        num_cols,
        ref_ids,
        names,
        data_types,
        lengths,
        precisions,
        scales,
        codepages,
        lineage_ids,
        dispositions,
    ):
        """All output columns are extracted with all metadata fields."""
        # Feature: pydtsx-parser, Property 2: Column Metadata Completeness

        columns_data = []
        for i in range(num_cols):
            columns_data.append(
                {
                    "refId": ref_ids[i],
                    "name": names[i],
                    "dataType": data_types[i],
                    "length": lengths[i],
                    "precision": precisions[i],
                    "scale": scales[i],
                    "codePage": codepages[i],
                    "lineageId": lineage_ids[i],
                    "errorRowDisposition": dispositions[i],
                    "truncationRowDisposition": dispositions[i],
                }
            )

        output_el = _build_output_element(columns_data)
        result = extract_output_columns(output_el)

        # Count must match
        assert len(result) == num_cols

        # Each column must have all expected fields
        for i, col in enumerate(result):
            assert col["ref_id"] == ref_ids[i]
            assert col["name"] == names[i]
            assert col["data_type"] == data_types[i]
            assert col["length"] == lengths[i]
            assert col["precision"] == precisions[i]
            assert col["scale"] == scales[i]
            assert col["code_page"] == codepages[i]
            assert col["lineage_id"] == lineage_ids[i]
            assert col["error_row_disposition"] == dispositions[i]
            assert col["truncation_row_disposition"] == dispositions[i]

    @given(
        num_cols=num_columns,
        ref_ids=st.lists(safe_identifier, min_size=5, max_size=5),
        names=st.lists(safe_identifier, min_size=5, max_size=5),
        data_types=st.lists(data_type_value, min_size=5, max_size=5),
        lengths=st.lists(int_attr_value, min_size=5, max_size=5),
        precisions=st.lists(int_attr_value, min_size=5, max_size=5),
        scales=st.lists(int_attr_value, min_size=5, max_size=5),
        codepages=st.lists(int_attr_value, min_size=5, max_size=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_external_metadata_columns_count_and_fields_match(
        self,
        num_cols,
        ref_ids,
        names,
        data_types,
        lengths,
        precisions,
        scales,
        codepages,
    ):
        """All external metadata columns are extracted with all metadata fields."""
        # Feature: pydtsx-parser, Property 2: Column Metadata Completeness

        columns_data = []
        for i in range(num_cols):
            columns_data.append(
                {
                    "refId": ref_ids[i],
                    "name": names[i],
                    "dataType": data_types[i],
                    "length": lengths[i],
                    "precision": precisions[i],
                    "scale": scales[i],
                    "codePage": codepages[i],
                }
            )

        parent_el = _build_external_metadata_element(columns_data)
        result = extract_external_metadata(parent_el)

        # Count must match
        assert len(result) == num_cols

        # Each column must have all expected fields
        for i, col in enumerate(result):
            assert col["ref_id"] == ref_ids[i]
            assert col["name"] == names[i]
            assert col["data_type"] == data_types[i]
            assert col["length"] == lengths[i]
            assert col["precision"] == precisions[i]
            assert col["scale"] == scales[i]
            assert col["code_page"] == codepages[i]


# --- Property 3: Component Classification Correctness ---
# Feature: pydtsx-parser, Property 3: Component Classification Correctness


class TestPropertyComponentClassificationCorrectness:
    """Property 3: Component Classification Correctness.

    For any componentClassID string, the parser SHALL return the correct
    classification from the known mapping when the ID matches a known entry,
    or "unknown" when it does not match, and in both cases SHALL still extract
    all component inputs, outputs, and properties.

    **Validates: Requirements 2.4, 2.5**
    """

    @given(class_id=st.sampled_from(known_class_ids))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_known_class_ids_return_correct_classification(self, class_id):
        """Known componentClassIDs return the correct classification."""
        # Feature: pydtsx-parser, Property 3: Component Classification Correctness

        expected = COMPONENT_CLASSIFICATION[class_id]
        result = classify_component(class_id)
        assert result == expected

    @given(
        class_id=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters="_."
            ),
            min_size=5,
            max_size=50,
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_unknown_class_ids_return_unknown(self, class_id):
        """Unknown componentClassIDs return 'unknown'."""
        # Feature: pydtsx-parser, Property 3: Component Classification Correctness

        assume(class_id not in COMPONENT_CLASSIFICATION)
        result = classify_component(class_id)
        assert result == "unknown"

    @given(
        class_id=component_class_id_strategy,
        comp_name=safe_identifier,
        comp_ref_id=safe_identifier,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_classification_does_not_affect_extraction_of_inputs_outputs(
        self,
        class_id,
        comp_name,
        comp_ref_id,
    ):
        """Classification does not prevent extraction of inputs, outputs, properties."""
        # Feature: pydtsx-parser, Property 3: Component Classification Correctness

        assume(class_id not in COMPONENT_CLASSIFICATION or True)  # all cases

        # Build a component with inputs and outputs
        output_cols = [
            {
                "refId": "out1",
                "name": "Col1",
                "dataType": "wstr",
                "length": "50",
                "precision": "0",
                "scale": "0",
                "codePage": "0",
                "lineageId": "100",
                "errorRowDisposition": "NotUsed",
                "truncationRowDisposition": "NotUsed",
            }
        ]

        comp_el = _build_component_element(
            ref_id=comp_ref_id,
            name=comp_name,
            class_id=class_id,
            output_columns=output_cols,
            num_inputs=1,
            num_outputs=1,
        )

        result = extract_component(comp_el)

        # Component must still be extracted (not failed)
        assert (
            "extraction_status" not in result
            or result.get("extraction_status") != "failed"
        )
        assert result["ref_id"] == comp_ref_id
        assert result["name"] == comp_name
        assert result["component_class_id"] == class_id

        # Classification must be correct
        expected_classification = COMPONENT_CLASSIFICATION.get(class_id, "unknown")
        assert result["classification"] == expected_classification

        # Inputs and outputs must be extracted
        assert isinstance(result["inputs"], list)
        assert isinstance(result["outputs"], list)
        assert len(result["inputs"]) == 1
        assert len(result["outputs"]) == 1

        # Output columns must be present
        assert len(result["outputs"][0]["output_columns"]) == 1


# --- Property 4: Lineage ID Preservation ---
# Feature: pydtsx-parser, Property 4: Lineage ID Preservation


class TestPropertyLineageIdPreservation:
    """Property 4: Lineage ID Preservation.

    For any data flow pipeline with components connected by lineageId references,
    the parser SHALL preserve all lineageId values such that for every inputColumn
    referencing an upstream outputColumn's lineageId, the same integer value
    appears in both the source component's output and the downstream component's
    input in the parsed output.

    **Validates: Requirements 2.5, 2.6**
    """

    @given(
        lineage_ids=st.lists(
            st.integers(min_value=1, max_value=99999),
            min_size=1,
            max_size=5,
            unique=True,
        ),
        source_name=safe_identifier,
        dest_name=safe_identifier,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_lineage_ids_preserved_between_source_and_destination(
        self,
        lineage_ids,
        source_name,
        dest_name,
    ):
        """lineageId values are preserved from output columns to input columns."""
        # Feature: pydtsx-parser, Property 4: Lineage ID Preservation

        # Build source component with output columns carrying lineageIds
        source_output_cols = []
        for lid in lineage_ids:
            source_output_cols.append(
                {
                    "refId": f"Source.Outputs[Out].Columns[Col{lid}]",
                    "name": f"Col{lid}",
                    "dataType": "wstr",
                    "length": "50",
                    "precision": "0",
                    "scale": "0",
                    "codePage": "0",
                    "lineageId": str(lid),
                    "errorRowDisposition": "NotUsed",
                    "truncationRowDisposition": "NotUsed",
                }
            )

        source_el = _build_component_element(
            ref_id="Package\\Source",
            name=source_name,
            class_id="Microsoft.OLEDBSource",
            output_columns=source_output_cols,
            num_inputs=0,
            num_outputs=1,
        )

        # Build destination component with input columns referencing the same lineageIds
        dest_input_cols = []
        for lid in lineage_ids:
            dest_input_cols.append(
                {
                    "refId": f"Dest.Inputs[In].Columns[Col{lid}]",
                    "cachedName": f"Col{lid}",
                    "cachedDataType": "wstr",
                    "cachedLength": "50",
                    "cachedPrecision": "0",
                    "cachedScale": "0",
                    "cachedCodepage": "0",
                    "lineageId": str(lid),
                    "externalMetadataColumnId": "0",
                }
            )

        dest_el = _build_component_element(
            ref_id="Package\\Dest",
            name=dest_name,
            class_id="Microsoft.OLEDBDestination",
            input_columns=dest_input_cols,
            num_inputs=1,
            num_outputs=0,
        )

        # Extract both components
        source_result = extract_component(source_el)
        dest_result = extract_component(dest_el)

        # Gather lineageIds from source output columns
        source_lineage_ids = set()
        for output in source_result["outputs"]:
            for col in output["output_columns"]:
                if col["lineage_id"]:
                    source_lineage_ids.add(int(col["lineage_id"]))

        # Gather lineageIds from destination input columns
        dest_lineage_ids = set()
        for inp in dest_result["inputs"]:
            for col in inp["input_columns"]:
                if col["lineage_id"]:
                    dest_lineage_ids.add(int(col["lineage_id"]))

        # Every lineageId in the original data must appear in both parsed outputs
        original_ids = set(lineage_ids)
        assert source_lineage_ids == original_ids, (
            f"Source lineage IDs mismatch: expected {original_ids}, got {source_lineage_ids}"
        )
        assert dest_lineage_ids == original_ids, (
            f"Dest lineage IDs mismatch: expected {original_ids}, got {dest_lineage_ids}"
        )

        # The same integer values appear in both
        assert source_lineage_ids == dest_lineage_ids, (
            f"Lineage IDs not preserved: source={source_lineage_ids}, dest={dest_lineage_ids}"
        )


# --- Property 15: Topological Sort Validity ---
# Feature: pydtsx-parser, Property 15: Topological Sort Validity


class TestPropertyTopologicalSortValidity:
    """Property 15: Topological Sort Validity.

    For any data flow pipeline with path elements connecting components, the
    parser's computed topological order SHALL be a valid topological ordering —
    meaning for every path edge from component A's output to component B's input,
    component A appears before component B in the ordering.

    **Validates: Requirements 11.2**
    """

    @given(
        num_components=st.integers(min_value=2, max_value=6),
        data=st.data(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_topological_order_respects_all_path_edges(
        self,
        num_components,
        data,
    ):
        """Every path edge A→B is respected in the topological order (A before B)."""
        # Feature: pydtsx-parser, Property 15: Topological Sort Validity

        # Generate unique component names
        comp_names = [f"Component_{i}" for i in range(num_components)]

        # Build components with inputs and outputs that have unique ref_ids
        components = []
        for i, name in enumerate(comp_names):
            comp = {
                "name": name,
                "ref_id": f"Package\\{name}",
                "inputs": [
                    {"ref_id": f"Package\\{name}.Inputs[Input0]", "name": "Input0"}
                ],
                "outputs": [
                    {"ref_id": f"Package\\{name}.Outputs[Output0]", "name": "Output0"}
                ],
            }
            components.append(comp)

        # Generate a valid DAG: for a linear chain plus some forward edges
        # Ensure acyclicity by only allowing edges from lower index to higher index
        paths = []
        # Always create a chain to ensure connectivity
        for i in range(num_components - 1):
            paths.append(
                {
                    "ref_id": f"Path_{i}",
                    "name": f"Path {comp_names[i]} to {comp_names[i + 1]}",
                    "start_id": f"Package\\{comp_names[i]}.Outputs[Output0]",
                    "end_id": f"Package\\{comp_names[i + 1]}.Inputs[Input0]",
                }
            )

        # Optionally add extra forward edges (always from lower to higher index)
        if num_components > 2:
            num_extra_edges = data.draw(
                st.integers(min_value=0, max_value=min(3, num_components - 2)),
                label="num_extra_edges",
            )
            for _ in range(num_extra_edges):
                src_idx = data.draw(
                    st.integers(min_value=0, max_value=num_components - 3),
                    label="src_idx",
                )
                dst_idx = data.draw(
                    st.integers(min_value=src_idx + 2, max_value=num_components - 1),
                    label="dst_idx",
                )
                paths.append(
                    {
                        "ref_id": f"Path_extra_{src_idx}_{dst_idx}",
                        "name": f"Path {comp_names[src_idx]} to {comp_names[dst_idx]}",
                        "start_id": f"Package\\{comp_names[src_idx]}.Outputs[Output0]",
                        "end_id": f"Package\\{comp_names[dst_idx]}.Inputs[Input0]",
                    }
                )

        # Compute topological order
        result = compute_topological_order(components, paths)

        # Result must contain all component names
        assert set(result) == set(comp_names), (
            f"Topological order missing components: expected {set(comp_names)}, got {set(result)}"
        )

        # Build position map for quick lookup
        position = {name: idx for idx, name in enumerate(result)}

        # For every path edge, the source must come before the destination
        output_to_comp = {}
        input_to_comp = {}
        for comp in components:
            for out in comp["outputs"]:
                output_to_comp[out["ref_id"]] = comp["name"]
            for inp in comp["inputs"]:
                input_to_comp[inp["ref_id"]] = comp["name"]

        for path in paths:
            source_comp = output_to_comp.get(path["start_id"])
            dest_comp = input_to_comp.get(path["end_id"])
            if source_comp and dest_comp and source_comp != dest_comp:
                assert position[source_comp] < position[dest_comp], (
                    f"Topological order violated: {source_comp} (pos {position[source_comp]}) "
                    f"should come before {dest_comp} (pos {position[dest_comp]})"
                )

    @given(
        num_components=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_no_paths_preserves_original_order(self, num_components):
        """When no paths exist, original component order is preserved."""
        # Feature: pydtsx-parser, Property 15: Topological Sort Validity

        comp_names = [f"Component_{i}" for i in range(num_components)]
        components = []
        for name in comp_names:
            components.append(
                {
                    "name": name,
                    "ref_id": f"Package\\{name}",
                    "inputs": [
                        {"ref_id": f"Package\\{name}.Inputs[Input0]", "name": "Input0"}
                    ],
                    "outputs": [
                        {
                            "ref_id": f"Package\\{name}.Outputs[Output0]",
                            "name": "Output0",
                        }
                    ],
                }
            )

        result = compute_topological_order(components, [])

        assert result == comp_names, (
            f"Without paths, order should be preserved: expected {comp_names}, got {result}"
        )
