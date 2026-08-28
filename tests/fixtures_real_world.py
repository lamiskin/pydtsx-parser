"""Paths to the real-world SSIS fixtures shared by the test suite."""

from pathlib import Path

REAL_WORLD_DIR = Path(__file__).resolve().parent / "fixtures" / "real_world"

U2_TOOLKIT_DIR = REAL_WORLD_DIR / "u2_toolkit"
SSIS_EXAMPLES_DIR = REAL_WORLD_DIR / "ssis_examples"

PROJECT_DTPROJ = U2_TOOLKIT_DIR / "Project.dtproj"
PROJECT_PARAMS = SSIS_EXAMPLES_DIR / "Project.params"

ALL_DTSX = sorted(REAL_WORLD_DIR.rglob("*.dtsx"))


def dtsx_id(path: Path) -> str:
    """Readable pytest id such as ``u2_toolkit/Package.dtsx``."""
    return f"{path.parent.name}/{path.name}"
