"""Integration tests for SSIS Parser against local example projects in examples/.

These tests parse SSIS .dtsx files from a local examples/ directory (not included in this repository)
and verify that the parser extracts the expected structural data. They validate
component counts, SQL task content, precedence constraints, transformations,
and completeness summary accuracy.

Tests are skipped if the example files are not present on the filesystem.
"""

import os
import xml.etree.ElementTree as ET

import pytest

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.extractors.pipeline import extract_pipeline
from pydtsx_parser.extractors.precedence import extract_precedence_constraints
from pydtsx_parser.extractors.sql_tasks import extract_sql_task, is_sql_task
from pydtsx_parser.parsers.dtsx import parse_dtsx
from pydtsx_parser.xml_utils import count_elements_and_attributes, parse_xml

DTS_NS = NAMESPACES["DTS"]

# Base path for example projects (relative to project root)
_EXAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "examples",
)

# File paths for each project
SAMPLE_ALPHA_PATH = os.path.join(
    _EXAMPLES_DIR, "SampleAlpha", "SampleAlpha", "Package.dtsx"
)
SAMPLE_BETA_PATH = os.path.join(
    _EXAMPLES_DIR,
    "SampleBeta",
    "SampleBeta",
    "SampleBeta",
    "Package.dtsx",
)
SAMPLE_GAMMA_PATH = os.path.join(
    _EXAMPLES_DIR,
    "SampleGamma",
    "SampleGamma",
    "SampleGamma",
    "Package.dtsx",
)


def _find_pipeline_executables(tree: ET.ElementTree) -> list[ET.Element]:
    """Find all Microsoft.Pipeline executable elements in a parsed tree."""
    root = tree.getroot()
    pipelines = []
    for elem in root.iter(f"{{{DTS_NS}}}Executable"):
        creation_name = elem.get(f"{{{DTS_NS}}}CreationName", "")
        if creation_name == "Microsoft.Pipeline":
            pipelines.append(elem)
    return pipelines


def _find_sql_task_executables(tree: ET.ElementTree) -> list[ET.Element]:
    """Find all SQL task executable elements in a parsed tree."""
    root = tree.getroot()
    tasks = []
    for elem in root.iter(f"{{{DTS_NS}}}Executable"):
        creation_name = elem.get(f"{{{DTS_NS}}}CreationName", "")
        if is_sql_task(creation_name):
            tasks.append(elem)
    return tasks


def _get_all_components(tree: ET.ElementTree) -> list[dict]:
    """Extract all data flow components from all pipelines in a tree."""
    all_components = []
    for pipe_elem in _find_pipeline_executables(tree):
        df = extract_pipeline(pipe_elem)
        all_components.extend(df.get("components", []))
    return all_components


# =============================================================================
# SampleAlpha Tests
# =============================================================================


@pytest.mark.integration
class TestSampleAlpha:
    """Integration tests for the SampleAlpha package."""

    @pytest.fixture(autouse=True)
    def setup(self):
        if not os.path.exists(SAMPLE_ALPHA_PATH):
            pytest.skip(f"File not found: {SAMPLE_ALPHA_PATH}")
        self.result = parse_dtsx(SAMPLE_ALPHA_PATH)
        self.tree = parse_xml(SAMPLE_ALPHA_PATH)

    def test_parses_without_errors(self):
        """Package parses successfully with a completeness summary."""
        assert "completeness_summary" in self.result
        assert self.result["completeness_summary"]["total_elements"] > 0

    def test_contains_oracle_sources(self):
        """Package contains Oracle source components."""
        all_comps = _get_all_components(self.tree)
        oracle_sources = [
            c for c in all_comps if "OracleSrc" in c.get("component_class_id", "")
        ]
        assert len(oracle_sources) >= 1

    def test_oracle_sources_classified_as_source(self):
        """All Oracle source components are classified as 'source'."""
        all_comps = _get_all_components(self.tree)
        oracle_sources = [
            c for c in all_comps if "OracleSrc" in c.get("component_class_id", "")
        ]
        for comp in oracle_sources:
            assert comp.get("classification") == "source"

    def test_contains_oledb_destinations(self):
        """Package contains OLE DB destination components."""
        all_comps = _get_all_components(self.tree)
        oledb_dests = [
            c for c in all_comps if "OLEDBDest" in c.get("component_class_id", "")
        ]
        assert len(oledb_dests) >= 1

    def test_oledb_destinations_classified_as_destination(self):
        """All OLE DB destination components are classified as 'destination'."""
        all_comps = _get_all_components(self.tree)
        oledb_dests = [
            c for c in all_comps if "OLEDBDest" in c.get("component_class_id", "")
        ]
        for comp in oledb_dests:
            assert comp.get("classification") == "destination"

    def test_components_have_column_metadata(self):
        """Each source/destination component has column metadata in outputs or inputs."""
        all_comps = _get_all_components(self.tree)
        oracle_sources = [
            c for c in all_comps if "OracleSrc" in c.get("component_class_id", "")
        ]
        for comp in oracle_sources:
            outputs = comp.get("outputs", [])
            # Every Oracle source should have at least one output with columns
            non_error_outputs = [o for o in outputs if not o.get("is_error_out", False)]
            assert len(non_error_outputs) > 0, (
                f"Oracle source '{comp.get('name')}' has no non-error outputs"
            )
            for output in non_error_outputs:
                output_cols = output.get("output_columns", [])
                assert len(output_cols) > 0, (
                    f"Oracle source '{comp.get('name')}' output has no columns"
                )

    def test_completeness_summary_matches_independent_count(self):
        """Completeness summary counts match independent XML counting."""
        cs = self.result["completeness_summary"]
        ind_elements, ind_attributes, _ = count_elements_and_attributes(self.tree)
        assert cs["total_elements"] == ind_elements
        assert cs["total_attributes"] == ind_attributes


# =============================================================================
# SampleBeta Tests
# =============================================================================


@pytest.mark.integration
class TestSampleBeta:
    """Integration tests for the SampleBeta package."""

    @pytest.fixture(autouse=True)
    def setup(self):
        if not os.path.exists(SAMPLE_BETA_PATH):
            pytest.skip(f"File not found: {SAMPLE_BETA_PATH}")
        self.result = parse_dtsx(SAMPLE_BETA_PATH)
        self.tree = parse_xml(SAMPLE_BETA_PATH)

    def test_parses_without_errors(self):
        """Package parses successfully with a completeness summary."""
        assert "completeness_summary" in self.result
        assert self.result["completeness_summary"]["total_elements"] > 0

    def test_contains_execute_sql_task(self):
        """Package contains an ExecuteSQLTask executable."""
        sql_tasks = _find_sql_task_executables(self.tree)
        assert len(sql_tasks) >= 1

    def test_sql_task_has_multi_statement_truncate(self):
        """The SQL task contains multiple TRUNCATE TABLE statements."""
        sql_tasks = _find_sql_task_executables(self.tree)
        assert len(sql_tasks) >= 1

        sql_data = extract_sql_task(sql_tasks[0], SAMPLE_BETA_PATH)
        sql_source = sql_data.get("sql_statement_source", "")

        # Should contain multiple TRUNCATE statements
        truncate_count = sql_source.upper().count("TRUNCATE")
        assert truncate_count > 1, (
            f"Expected multiple TRUNCATE statements, found {truncate_count}"
        )

    def test_data_flow_has_flat_file_sources(self):
        """Data flow task contains flat file source components."""
        all_comps = _get_all_components(self.tree)
        flat_sources = [
            c for c in all_comps if "FlatFileSource" in c.get("component_class_id", "")
        ]
        assert len(flat_sources) >= 1

    def test_data_flow_has_oledb_destinations(self):
        """Data flow task contains OLE DB destination components."""
        all_comps = _get_all_components(self.tree)
        oledb_dests = [
            c for c in all_comps if "OLEDBDest" in c.get("component_class_id", "")
        ]
        assert len(oledb_dests) >= 1

    def test_completeness_summary_matches_independent_count(self):
        """Completeness summary counts match independent XML counting."""
        cs = self.result["completeness_summary"]
        ind_elements, ind_attributes, _ = count_elements_and_attributes(self.tree)
        assert cs["total_elements"] == ind_elements
        assert cs["total_attributes"] == ind_attributes


# =============================================================================
# SampleGamma Tests
# =============================================================================


@pytest.mark.integration
class TestSampleGamma:
    """Integration tests for the SampleGamma package."""

    @pytest.fixture(autouse=True)
    def setup(self):
        if not os.path.exists(SAMPLE_GAMMA_PATH):
            pytest.skip(f"File not found: {SAMPLE_GAMMA_PATH}")
        self.result = parse_dtsx(SAMPLE_GAMMA_PATH)
        self.tree = parse_xml(SAMPLE_GAMMA_PATH)

    def test_parses_without_errors(self):
        """Package parses successfully with a completeness summary."""
        assert "completeness_summary" in self.result
        assert self.result["completeness_summary"]["total_elements"] > 0

    def test_contains_precedence_constraints(self):
        """Package contains precedence constraints."""
        root = self.tree.getroot()
        constraints = extract_precedence_constraints(root, SAMPLE_GAMMA_PATH)
        assert len(constraints) >= 1

    def test_precedence_constraints_have_from_and_to(self):
        """Each precedence constraint has non-empty from_task and to_task."""
        root = self.tree.getroot()
        constraints = extract_precedence_constraints(root, SAMPLE_GAMMA_PATH)
        for constraint in constraints:
            assert constraint.get("from_task"), (
                f"Constraint '{constraint.get('object_name')}' has empty from_task"
            )
            assert constraint.get("to_task"), (
                f"Constraint '{constraint.get('object_name')}' has empty to_task"
            )

    def test_contains_derived_column_transforms(self):
        """Package contains derived column transformation components."""
        all_comps = _get_all_components(self.tree)
        derived_cols = [
            c for c in all_comps if "DerivedColumn" in c.get("component_class_id", "")
        ]
        assert len(derived_cols) >= 1

    def test_derived_columns_have_crlf_stripping_expressions(self):
        """At least one derived column component has CRLF-stripping expressions."""
        all_comps = _get_all_components(self.tree)
        derived_cols = [
            c for c in all_comps if "DerivedColumn" in c.get("component_class_id", "")
        ]

        has_crlf_stripping = False
        for comp in derived_cols:
            dc_columns = comp.get("derived_columns", [])
            for col in dc_columns:
                expression = col.get("expression", "") or ""
                if "REPLACE" in expression:
                    has_crlf_stripping = True
                    break
            if has_crlf_stripping:
                break

        assert has_crlf_stripping, (
            "No derived column component found with CRLF-stripping REPLACE expressions"
        )

    def test_contains_merge_join_configurations(self):
        """Package contains merge join components with join types."""
        all_comps = _get_all_components(self.tree)
        merge_joins = [
            c for c in all_comps if "MergeJoin" in c.get("component_class_id", "")
        ]
        assert len(merge_joins) >= 1

        # Verify join types are extracted
        join_types = [mj.get("join_type", "") for mj in merge_joins]
        assert any(jt in ("INNER", "LEFT", "FULL") for jt in join_types), (
            f"No recognized join types found: {join_types}"
        )

    def test_contains_sort_components(self):
        """Package contains sort transformation components."""
        all_comps = _get_all_components(self.tree)
        sorts = [
            c for c in all_comps if c.get("component_class_id", "") == "Microsoft.Sort"
        ]
        assert len(sorts) >= 1

    def test_sort_components_have_eliminate_duplicates_property(self):
        """Sort components have the EliminateDuplicates custom property."""
        all_comps = _get_all_components(self.tree)
        sorts = [
            c for c in all_comps if c.get("component_class_id", "") == "Microsoft.Sort"
        ]
        for sort_comp in sorts:
            custom_props = sort_comp.get("custom_properties", [])
            prop_names = [p.get("name", "") for p in custom_props]
            assert "EliminateDuplicates" in prop_names, (
                f"Sort '{sort_comp.get('name')}' missing EliminateDuplicates property"
            )

    def test_completeness_summary_matches_independent_count(self):
        """Completeness summary counts match independent XML counting."""
        cs = self.result["completeness_summary"]
        ind_elements, ind_attributes, _ = count_elements_and_attributes(self.tree)
        assert cs["total_elements"] == ind_elements
        assert cs["total_attributes"] == ind_attributes
