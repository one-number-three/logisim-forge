"""Command line entry point: python -m logisim_forge {serve,verify}."""
from __future__ import annotations

import argparse
import json

from .verify import verify


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="logisim_forge")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="run the MCP server on stdio")
    p_verify = sub.add_parser("verify", help="load a .circ with Logisim and audit it")
    p_verify.add_argument("path")
    args = ap.parse_args(argv)

    if args.cmd == "serve":
        from .server import main as serve
        serve()
        return 0

    report = verify(args.path)
    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
