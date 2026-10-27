"""MCP server: let an agent design Logisim circuits with code.

Every add_* tool returns the component's *port coordinates*; wire those exact
points and the circuit is connected.  This is the whole trick - the model never
has to guess Logisim's geometry.
"""
from __future__ import annotations

from typing import Any

from .circuit import Circuit

try:  # pragma: no cover - exercised only when the MCP SDK is installed
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover
    FastMCP = None  # type: ignore

_CIRCUITS: dict[str, Circuit] = {}
_PATHS: dict[str, str] = {}


def _get(name: str) -> Circuit:
    if name not in _CIRCUITS:
        raise ValueError("unknown circuit %r - call create_circuit first" % name)
    return _CIRCUITS[name]


def _pts(points) -> list[list[int]]:
    return [list(p) for p in points]


def build_server():
    mcp = FastMCP("logisim")

    @mcp.tool()
    def create_circuit(name: str = "main") -> dict:
        """Start a new empty circuit. Returns its name."""
        _CIRCUITS[name] = Circuit(name)
        return {"circuit": name, "components": 0}

    @mcp.tool()
    def add_pin(circuit: str, x: int, y: int, label: str, direction: str = "in") -> dict:
        """Add a pin. direction='in' drives the circuit, 'out' displays a value.

        Returns port=[x,y]; connect a wire exactly to that point.
        """
        c = _get(circuit)
        facing = "east" if direction == "in" else "west"
        c.pin((x, y), label, direction=direction, facing=facing)
        return {"label": label, "direction": direction, "port": [x, y]}

    @mcp.tool()
    def add_gate(circuit: str, kind: str, x: int, y: int,
                 inputs: int = 2, negated: list[int] | None = None) -> dict:
        """Add a gate. kind in {NOT, AND, OR, NAND, NOR, XOR, XNOR}.

        (x, y) is the OUTPUT port. Returns every port: index 0 is the output,
        the rest are inputs in top-to-bottom order. negated=[1,2] draws bubbles.
        """
        c = _get(circuit)
        name = kind if kind.endswith("Gate") else kind + " Gate"
        negs = tuple(negated or ())
        if name == "NOT Gate":
            comp = c.not_gate((x, y))
        elif name == "AND Gate":
            comp = c.and_gate((x, y), inputs, negs)
        elif name == "NAND Gate":
            comp = c.nand_gate((x, y), inputs, negs)
        elif name == "OR Gate":
            comp = c.or_gate((x, y), inputs, negs)
        elif name in ("NOR Gate", "XOR Gate", "XNOR Gate"):
            comp = c._add(2, name, (x, y), [("inputs", str(inputs))] + [("negate%d" % i, "true") for i in negs])
        else:
            raise ValueError("unsupported gate %r" % kind)
        ports = c.ports()[id(comp)]
        return {"kind": name, "ports": _pts(ports), "output": [x, y], "inputs": _pts(ports[1:])}

    @mcp.tool()
    def add_led(circuit: str, x: int, y: int, label: str = "") -> dict:
        """Add an LED whose input port is at (x, y)."""
        c = _get(circuit)
        comp = c.led((x, y), label=label)
        return {"port": [x, y], "component": comp["name"]}

    @mcp.tool()
    def add_wire(circuit: str, points: list[list[int]]) -> dict:
        """Add an orthogonal wire through the given points.

        Segments must be horizontal or vertical (Logisim hangs on diagonals).
        A wire end that lands on another wire or on a port is a connection;
        two wires merely crossing are NOT connected.
        """
        c = _get(circuit)
        pts = [tuple(p) for p in points]
        c.wire(*pts)
        return {"segments": len(pts) - 1, "from": list(pts[0]), "to": list(pts[-1])}

    @mcp.tool()
    def list_components(circuit: str) -> dict:
        """List components with their ports, so wires can be re-routed."""
        c = _get(circuit)
        ports = c.ports()
        return {"circuit": circuit, "components": [
            {"name": comp["name"], "loc": list(comp["loc"]), "ports": _pts(ports[id(comp)])}
            for comp in c.comps]}

    @mcp.tool()
    def save_circuit(circuit: str, path: str) -> dict:
        """Write the .circ file (UTF-8 XML, Logisim 2.7 compatible)."""
        c = _get(circuit)
        c.save(path)
        _PATHS[circuit] = path
        return {"path": path, "components": len(c.comps), "wires": len(c.wires)}

    @mcp.tool()
    def verify_circuit(path: str) -> dict:
        """Check physical-wire topology per circuit. Tunnels and splitter bits
        are not resolved; use simulate_vectors for functional validation."""
        from .simulate import inspect
        return inspect(path)

    @mcp.tool()
    def simulate_vectors(path: str, circuit: str, vectors_csv: str, image_path: str = '') -> dict:
        """Load a .circ in real Logisim, drive all input pins and check all outputs.
        CSV header must list every pin label and may include @x:y net checks.
        Each row includes inputs and expected outputs as decimal integers; rows
        share state in order, so clock 0->1 drives sequential circuits. Fails on
        unknown/error values, width mismatch, oscillation or mismatches. Optional
        PNG shows the final native simulated state. Only tested with Logisim-ITA.
        """
        from .simulate import simulate
        return simulate(path, circuit, vectors_csv, image_path)

    @mcp.tool()
    def inspect_project(path: str) -> dict:
        """Return circuit-scoped topology checks from the real Logisim loader."""
        from .simulate import inspect
        return inspect(path)

    return mcp


def main() -> None:  # pragma: no cover
    if FastMCP is None:
        raise SystemExit("the 'mcp' package is not installed: pip install mcp")
    build_server().run()


if __name__ == "__main__":  # pragma: no cover
    main()
