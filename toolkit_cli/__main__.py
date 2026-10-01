"""``python -m toolkit_cli`` forwards to ``python -m formwork_cli`` (ADR 0010)."""

import sys

from formwork_cli.cli import main


if __name__ == "__main__":
    print(
        "toolkit_cli is now formwork_cli; run 'python -m formwork_cli' instead. "
        "This alias will be removed in Formwork 0.4.0.",
        file=sys.stderr,
    )
    raise SystemExit(main())
