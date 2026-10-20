"""Logisim component geometry.

Logisim snaps everything to a 10 px grid.  A component's "loc" is NOT the
top-left corner of its bounding box: for gates it is the *output* port, for
pins it is the only port.  Input ports hang off to the left, and their vertical
offsets depend on how many inputs the gate has (Logisim spreads them over the
gate body and skips the centre row when the count is even).

These tables were measured from real Logisim 2.7 / 2.16 files - see
docs/pitfalls.md for how they were obtained.
"""
from __future__ import annotations

GRID = 10

#: vertical offsets of the input ports, relative to the gate's loc
GATE_PORT_DY: dict[int, tuple[int, ...]] = {
    2: (-20, 20),
    3: (-20, 0, 20),
    4: (-20, -10, 10, 20),
    5: (-20, -10, 0, 10, 20),
    8: (-40, -30, -20, -10, 10, 20, 30, 40),
}

AND_BODY_W = 50      # bounding box width of an AND gate
NAND_BODY_W = 60     # +10 for the output bubble
NOT_BODY_W = 30      # NOT gate: input is 30 px left of the output


def check_grid(*points: tuple[int, int]) -> None:
    for x, y in points:
        if x % GRID or y % GRID:
            raise ValueError("point %r is not on the %dpx grid" % ((x, y), GRID))


def gate_inputs(kind: str, loc: tuple[int, int], inputs: int,
                negated=()) -> list[tuple[int, int]]:
    """Input port locations of a gate whose output port sits at loc.

    A bubble on an input pushes *that* port another 10 px to the left, so the
    left edge of the gate is not straight once anything is negated.
    """
    if kind == "NOT Gate":
        return [(loc[0] - NOT_BODY_W, loc[1])]
    dy = GATE_PORT_DY[inputs]
    base = NAND_BODY_W if kind == "NAND Gate" else AND_BODY_W
    return [(loc[0] - base - (10 if i in negated else 0), loc[1] + d)
            for i, d in enumerate(dy)]


def gate_ports(kind: str, loc: tuple[int, int], inputs: int = 2,
               negated=()) -> list[tuple[int, int]]:
    return [loc] + gate_inputs(kind, loc, inputs, negated)


def bounds(kind: str, loc: tuple[int, int], inputs: int = 2):
    """(x, y, w, h) of a component, for layout and overlap checks."""
    if kind == "Pin":
        return (loc[0] - 25, loc[1] - 10, 25, 20)
    if kind == "LED":
        return (loc[0], loc[1] - 10, 20, 20)
    if kind == "NOT Gate":
        return (loc[0] - NOT_BODY_W, loc[1] - 9, NOT_BODY_W, 18)
    dy = GATE_PORT_DY[inputs]
    h = max(dy) - min(dy) + 20
    w = NAND_BODY_W if kind == "NAND Gate" else AND_BODY_W
    return (loc[0] - w, loc[1] - h // 2, w, h)
