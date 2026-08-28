"""Entry point for running pydtsx_parser as a module: python -m pydtsx_parser."""

import sys

from pydtsx_parser.cli import main

if __name__ == "__main__":
    sys.exit(main())
