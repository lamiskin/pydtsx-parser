"""Tests against real-world SSIS packages published under permissive licences.

Unlike the hand-written XML in the rest of the suite, these fixtures are genuine
packages authored by Visual Studio and committed by third parties. They span
SSIS 2012 (`SSIS.Package.3`), 2014 and 2022 (`Microsoft.Package`), and exercise
attribute orderings, component class IDs, and namespace usage that synthetic
fixtures do not reproduce.

Provenance and sanitisation are documented in
``tests/fixtures/real_world/README.md``.
"""

import re

import pytest

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.extractors.pipeline import extract_pipeline
from pydtsx_parser.parsers.dtproj import parse_dtproj
from pydtsx_parser.parsers.dtsx import parse_dtsx
from pydtsx_parser.parsers.params import parse_params
from pydtsx_parser.xml_utils import parse_xml

from .fixtures_real_world import (
    ALL_DTSX,
    PROJECT_DTPROJ,
    PROJECT_PARAMS,
    REAL_WORLD_DIR,
    dtsx_id,
)
from .scrubbed_guard import find_scrubbed

DTS_NS = NAMESPACES["DTS"]

# Shapes that identify a person, host, or organisation regardless of whether
# anyone thought to add the literal string above. The named list is necessarily
# retrospective — every identifier missed so far was invisible to it but obvious
# to these — so this fails the build the first time an unfamiliar one appears.
_IDENTIFIER_SHAPES = (
    # UNC server names.
    re.compile(r"\\\\(?!BUILDHOST)[A-Za-z0-9_-]{2,}\\", re.IGNORECASE),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    # A OneDrive for Business path carries the tenant's organisation name.
    re.compile(r"OneDrive - [A-Za-z0-9][A-Za-z0-9 ._-]{2,}"),
    # Private-range addresses only. A bare dotted quad is too broad: SSIS writes
    # schema and product versions (`9.0.1.0`, `11.0.0.0`) that look identical,
    # and internal addresses that leak are RFC 1918 in practice.
    re.compile(r"\b(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)\d{1,3}\.\d{1,3}\b"),
    # Windows profile paths under a user name other than the synthetic one.
    re.compile(r"(?i)[A-Za-z]:\\Users\\(?!etluser\b)[A-Za-z0-9_.-]+"),
    # A local clone folder under `source\repos\`, one level below the profile
    # path above — the shape that let both ExampleRepo and SampleRepo through
    # unscrubbed the first time, since the user-name check does not look this
    # deep into the same path.
    re.compile(r"(?i)\\source\\repos\\(?!ExampleRepo\b|SampleRepo\b)[A-Za-z0-9._-]+"),
)


@pytest.mark.parametrize("path", ALL_DTSX, ids=dtsx_id)
def test_real_package_parses(path):
    """Every real package parses without raising."""
    result = parse_dtsx(str(path))
    assert result["package_attributes"]["object_name"]
    assert result["executables"], f"{path.name} extracted no executables"


@pytest.mark.parametrize("path", ALL_DTSX, ids=dtsx_id)
def test_real_package_is_fully_accounted_for(path):
    """The completeness summary reports no skipped items on real packages."""
    summary = parse_dtsx(str(path))["completeness_summary"]
    assert summary["skipped_items"] == []
    assert summary["total_elements"] > 0
    assert summary["total_attributes"] > 0


@pytest.mark.parametrize("path", ALL_DTSX, ids=dtsx_id)
def test_real_package_reports_package_format_metadata(path):
    """Real packages carry both package-format generations across SSIS 2012-2022."""
    attributes = parse_dtsx(str(path))["package_attributes"]
    assert attributes["creation_name"].startswith(("SSIS.Package", "Microsoft.Package"))
    assert attributes["dts_id"].startswith("{")
    assert attributes["version_guid"].startswith("{")


@pytest.mark.parametrize("path", ALL_DTSX, ids=dtsx_id)
def test_real_pipelines_extract_components_and_paths(path):
    """Each real package contains a data flow with wired-up components."""
    root = parse_xml(str(path)).getroot()
    pipelines = [
        element
        for element in root.iter(f"{{{DTS_NS}}}Executable")
        if "Pipeline" in (element.get(f"{{{DTS_NS}}}CreationName") or "")
    ]
    assert pipelines, f"{path.name} has no pipeline executable"

    for pipeline in pipelines:
        extracted = extract_pipeline(pipeline)
        components = extracted["components"]
        assert components, f"{path.name} pipeline extracted no components"
        assert all(component["name"] for component in components)
        # A data flow with N components is wired by at least one path.
        assert extracted["paths"], f"{path.name} pipeline extracted no paths"


def test_component_class_id_may_be_a_raw_guid():
    """Real packages reference components by GUID, not just by friendly name.

    ``U2 Toolkit/Package.dtsx`` uses a third-party pipeline component whose
    ``componentClassID`` is a bare GUID. Synthetic fixtures only ever use the
    ``Microsoft.*`` string form, so this asserts the GUID form survives parsing.
    """
    path = REAL_WORLD_DIR / "u2_toolkit" / "Package.dtsx"
    root = parse_xml(str(path)).getroot()
    pipeline = next(
        element
        for element in root.iter(f"{{{DTS_NS}}}Executable")
        if "Pipeline" in (element.get(f"{{{DTS_NS}}}CreationName") or "")
    )
    class_ids = [
        component["component_class_id"]
        for component in extract_pipeline(pipeline)["components"]
    ]
    assert any(
        class_id.startswith("{") and class_id.endswith("}") for class_id in class_ids
    )


def test_fixtures_cover_the_documented_version_spread():
    """Pin the SSIS version coverage the README advertises.

    The "Supported SSIS versions" table claims real-file coverage of both
    package-format generations across SSIS 2012, 2014 and 2022. If a fixture is
    swapped or dropped, that claim should fail here rather than go stale.
    """
    creation_names, major_versions = set(), set()
    for path in ALL_DTSX:
        attributes = parse_dtsx(str(path))["package_attributes"]
        creation_names.add(attributes["creation_name"])
        major_versions.add(attributes["last_modified_product_version"].split(".", 1)[0])

    # Both package-format generations: SSIS 2012 vs 2014-and-later.
    assert "SSIS.Package.3" in creation_names
    assert "Microsoft.Package" in creation_names
    # SQL Server 2012, 2014 and 2022 respectively.
    assert {"11", "12", "16"} <= major_versions


def test_real_dtproj_parses():
    """The real project manifest yields a deployment model and package list."""
    result = parse_dtproj(str(PROJECT_DTPROJ))
    assert result["success"] is True
    assert result["deployment_model"] == "Project"
    assert result["product_version"].startswith("11.")
    assert result["manifest"]["protection_level"]


def test_real_params_parses():
    """A real (empty) project parameter file parses to an empty parameter list."""
    assert parse_params(str(PROJECT_PARAMS)) == {"parameters": []}


@pytest.mark.parametrize(
    "path",
    sorted(p for p in REAL_WORLD_DIR.rglob("*") if p.is_file() and p.suffix != ".md"),
    ids=lambda p: p.name,
)
def test_fixtures_contain_no_unscrubbed_identifiers(path):
    """Guard: the committed fixtures must stay free of upstream identifiers.

    The identifiers are matched by hash rather than by literal, so that this
    repository does not itself publish the values the fixtures were sanitised to
    remove. See ``tests/scrubbed_guard.py``.
    """
    text = path.read_bytes().decode("utf-8", "replace")
    hit = find_scrubbed(text)
    assert hit is None, (
        f"{path.name} contains a known upstream identifier at byte offset "
        f"{hit[0]} (sha256 {hit[1][:12]}…). Re-run the sanitisation step; the "
        "procedure is in tests/fixtures/real_world/README.md."
    )


@pytest.mark.parametrize(
    "path",
    sorted(p for p in REAL_WORLD_DIR.rglob("*") if p.is_file() and p.suffix != ".md"),
    ids=lambda p: p.name,
)
def test_fixtures_contain_no_identifier_shaped_strings(path):
    """Guard: catch identifiers nobody thought to add to ``_SCRUBBED``.

    Asserts on the *shape* of a leak — an unfamiliar host, mailbox, tenant or
    private address fails immediately rather than waiting to be enumerated.
    """
    text = path.read_bytes().decode("utf-8", "replace")
    for pattern in _IDENTIFIER_SHAPES:
        found = pattern.search(text)
        assert found is None, (
            f"{path.name} contains {found.group(0)!r}, which looks like a real "
            "identifier. Sanitise it, then extend the substitution table in "
            "tests/fixtures/real_world/README.md."
        )
