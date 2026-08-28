"""CLI module for the SSIS Parser.

Provides argument parsing, output routing (stdout vs file), stderr
warning/error logging, and exit code handling.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from pydtsx_parser.dispatcher import SUPPORTED_EXTENSIONS, dispatch
from pydtsx_parser.errors import SSISParseError

logger = logging.getLogger("pydtsx_parser")


def parse_args(args: list[str]) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        args: List of command-line argument strings.

    Returns:
        Parsed argparse.Namespace with path, output, and pretty attributes.
    """
    parser = argparse.ArgumentParser(
        prog="pydtsx-parser",
        description="Parse SSIS files (.dtsx, .dtproj, .conmgr, .params) into JSON.",
    )
    parser.add_argument(
        "path",
        help="File or directory path to parse",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        default=False,
        help="Pretty-print JSON with 2-space indent",
    )
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """Entry point for the SSIS Parser CLI.

    Parses arguments, dispatches to the appropriate parser, and routes
    output to stdout or a file. Logs warnings/errors to stderr.

    Args:
        args: Optional list of CLI arguments. If None, uses sys.argv[1:].

    Returns:
        Exit code: 0 for success, non-zero for errors.
    """
    # Configure stderr logging for warnings and errors
    logging.basicConfig(
        stream=sys.stderr,
        format="%(levelname)s: %(message)s",
        level=logging.WARNING,
    )

    if args is None:
        args = sys.argv[1:]

    parsed = parse_args(args)
    path = parsed.path
    output_path = parsed.output
    pretty = parsed.pretty

    # Resolve the path
    resolved = Path(path).resolve()

    # Check if path exists
    if not resolved.exists():
        print(f"Error: Path does not exist: {resolved}", file=sys.stderr)
        return 1

    # For single files, check if the extension is supported
    if resolved.is_file():
        ext = resolved.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            logger.warning("Unsupported file type '%s': %s (skipping)", ext, resolved)
            return 0

    # Dispatch parsing
    try:
        result = dispatch(str(resolved), pretty=pretty)
    except SSISParseError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: Unexpected error: {e}", file=sys.stderr)
        return 1

    # Serialize to JSON
    indent = 2 if pretty else None
    json_output = json.dumps(result, indent=indent, ensure_ascii=False)

    # Route output
    if output_path:
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(json_output, encoding="utf-8")
        except OSError as e:
            print(f"Error: Cannot write to output file: {e}", file=sys.stderr)
            return 1
    else:
        print(json_output)

    return 0
