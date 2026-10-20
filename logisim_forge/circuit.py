"""Build a Logisim .circ file programmatically."""
from __future__ import annotations

import xml.sax.saxutils as sax

from . import geometry

WIRING, GATES, IO = 0, 1, 2


class Circuit:
    """In-memory circuit that serialises to Logisim's XML format."""

    def __init__(self, name: str = "main") -> None:
        self.name = name
        self.comps: list[dict] = []
        self.wires: list[tuple[tuple[int, int], tuple[int, int]]] = []

    # ------------------------------------------------------------------ parts
    def _add(self, lib: int, name: str, loc, attrs=()) -> dict:
        geometry.check_grid(loc)
        comp = {"lib": lib, "name": name, "loc": loc, "attrs": list(attrs)}
        self.comps.append(comp)
        return comp

    def pin(self, loc, label, direction="in", facing="east", labelloc="east"):
        """direction="in" is a *source* (logisim attr output=false)."""
        return self._add(WIRING, "Pin", loc, [
            ("facing", facing),
            # Logisim's attribute is literally called "output":
            # False for an input pin (a driver), True for an output pin.
            ("output", "true" if direction == "out" else "false"),
            # ITA builds default this to true, which leaves the pin floating.
            ("tristate", "false"),
            ("label", label),
            ("labelloc", labelloc),
        ])

    def not_gate(self, loc):
        return self._add(GATES, "NOT Gate", loc)

    def and_gate(self, loc, inputs=2, negated=()):
        attrs = [("inputs", str(inputs))] + [("negate%d" % i, "true") for i in negated]
        return self._add(GATES, "AND Gate", loc, attrs)

    def nand_gate(self, loc, inputs=2, negated=()):
        attrs = [("inputs", str(inputs))] + [("negate%d" % i, "true") for i in negated]
        return self._add(GATES, "NAND Gate", loc, attrs)

    def or_gate(self, loc, inputs=2, negated=()):
        attrs = [("inputs", str(inputs))] + [("negate%d" % i, "true") for i in negated]
        return self._add(GATES, "OR Gate", loc, attrs)

    def led(self, loc, color="red", facing="west", label=""):
        return self._add(IO, "LED", loc, [("facing", facing), ("color", color),
                                          ("label", label), ("labelloc", "north")])

    # ------------------------------------------------------------------ wires
    def wire(self, *points):
        """Add an orthogonal polyline through points."""
        geometry.check_grid(*points)
        for a, b in zip(points, points[1:]):
            if a[0] != b[0] and a[1] != b[1]:
                raise ValueError("diagonal segment %r->%r: Logisim hangs on those" % (a, b))
            if a != b:
                self.wires.append((a, b))

    # ------------------------------------------------------------------- info
    def ports(self):
        """id(comp) -> port locations (output port first)."""
        out = {}
        for c in self.comps:
            if c["name"] in ("Pin", "LED"):
                out[id(c)] = [c["loc"]]
            else:
                attrs = dict(c["attrs"])
                inputs = int(attrs.get("inputs", 2))
                negs = {int(k[6:]) for k, v in attrs.items() if k.startswith("negate") and v == "true"}
                out[id(c)] = geometry.gate_ports(c["name"], c["loc"], inputs, negs)
        return out

    def drivers(self):
        """Ports that drive a value (input pins and gate outputs)."""
        res = []
        for c in self.comps:
            attrs = dict(c["attrs"])
            if c["name"] == "Pin":
                if attrs.get("output") == "false":
                    res.append((c["loc"], "pin:%s" % attrs.get("label", "")))
            elif c["name"].endswith("Gate"):
                res.append((c["loc"], c["name"]))
        return res

    # ------------------------------------------------------------------- save
    def to_xml(self) -> str:
        wires = self._split_wires()
        lines = [
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
            '<project source="2.7.1" version="1.0">',
            '  <lib desc="#Wiring" name="0"/>',
            '  <lib desc="#Gates" name="1"/>',
            '  <lib desc="#I/O" name="2"/>',
            '  <main name="%s"/>' % sax.escape(self.name),
            '  <options/>',
            '  <circuit name="%s">' % sax.escape(self.name),
            '    <a name="circuit" val="%s"/>' % sax.escape(self.name),
        ]
        for c in self.comps:
            x, y = c["loc"]
            lines.append('    <comp lib="%d" loc="(%d,%d)" name="%s">' % (c["lib"], x, y, c["name"]))
            for k, v in c["attrs"]:
                lines.append('      <a name="%s" val="%s"/>' % (k, sax.escape(v)))
            lines.append('    </comp>')
        for (x0, y0), (x1, y1) in wires:
            lines.append('    <wire from="(%d,%d)" to="(%d,%d)"/>' % (x0, y0, x1, y1))
        lines += ['  </circuit>', '</project>', '']
        return "\n".join(lines)

    def save(self, path: str) -> str:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_xml())
        return path

    def _split_wires(self):
        """Cut wires at every port/endpoint so connections are endpoint-to-endpoint.

        Logisim connects a wire end that touches another wire, while crossing
        wires stay separate.  Splitting here means the topology does not depend
        on Logisim's junction repair at all.
        """
        bend = set()
        for ports in self.ports().values():
            bend.update(ports)
        for a, b in self.wires:
            bend.add(a)
            bend.add(b)

        out = []
        for (x0, y0), (x1, y1) in self.wires:
            if x0 == x1:
                lo, hi = sorted((y0, y1))
                mid = sorted({p[1] for p in bend if p[0] == x0 and lo < p[1] < hi})
                seq = [lo] + mid + [hi]
                out += [((x0, seq[i]), (x0, seq[i + 1])) for i in range(len(seq) - 1)]
            else:
                lo, hi = sorted((x0, x1))
                mid = sorted({p[0] for p in bend if p[1] == y0 and lo < p[0] < hi})
                seq = [lo] + mid + [hi]
                out += [((seq[i], y0), (seq[i + 1], y0)) for i in range(len(seq) - 1)]
        return [w for w in out if w[0] != w[1]]
