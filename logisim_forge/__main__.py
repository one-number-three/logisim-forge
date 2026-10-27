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
    p_inspect = sub.add_parser("inspect", help="inspect topology per circuit")
    p_inspect.add_argument("path")
    p_sim = sub.add_parser("simulate", help="run sequential CSV vectors in Logisim")
    p_sim.add_argument("path")
    p_sim.add_argument("circuit")
    p_sim.add_argument("vectors_csv")
    p_sim.add_argument("--image", default="", help="optional PNG of final state")
    args = ap.parse_args(argv)

    if args.cmd == "serve":
        from .server import main as serve
        serve()
        return 0

    if args.cmd in ("simulate", "inspect"):
        from .simulate import inspect, simulate
        report = (simulate(args.path, args.circuit, args.vectors_csv, args.image)
                  if args.cmd == "simulate" else inspect(args.path))
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report['ok'] else 1

    report = verify(args.path)
    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
