"""Example: 74LS138-style 3-to-8 decoder, one output per minterm.

    python examples/74ls138.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logisim_forge import Circuit, normalize, verify  # noqa: E402

GX, Y0, STEP = 780, 520, 70
BUS = {"A": 540, "A_": 520, "B": 500, "B_": 480, "C": 460, "C_": 440}
SRC_Y = {"A": 220, "A_": 260, "B": 300, "B_": 340, "C": 380, "C_": 420}
OFF = [-20, -10, 10]


def build() -> Circuit:
    c = Circuit("main")

    # --- inputs ---------------------------------------------------------
    c.pin((110, 60), "G1")
    c.pin((110, 100), "G2A_L")
    c.pin((110, 140), "G2B_L")
    c.pin((110, 220), "A")
    c.pin((110, 300), "B")
    c.pin((110, 380), "C")

    # --- inverters ------------------------------------------------------
    c.not_gate((240, 60))     # ~G1
    c.not_gate((240, 260))    # ~A
    c.not_gate((240, 340))    # ~B
    c.not_gate((240, 420))    # ~C

    # --- enable term E = ~G1 & ~G2A & ~G2B (bubbles on the active-low pins)
    c.and_gate((420, 100), 3, negated=(1, 2))

    # --- 8 x 4-input NAND ----------------------------------------------
    ys = [Y0 + STEP * i for i in range(8)]
    for i, y in enumerate(ys):
        c.nand_gate((GX, y), 4)
        c.pin((880, y), "Y%d_L" % i, direction="out", facing="west")

    # --- enable chain wiring -------------------------------------------
    c.wire((110, 60), (210, 60))                      # G1 -> inverter
    c.wire((240, 60), (300, 60), (300, 80), (370, 80))
    # inputs 1 and 2 carry bubbles, so their ports are 10 px further left
    c.wire((110, 100), (360, 100))
    c.wire((110, 140), (320, 140), (320, 120), (360, 120))
    c.wire((420, 100), (600, 100))                    # E trunk

    # --- address: trunk + inverter + vertical bus ----------------------
    for name in ("A", "B", "C"):
        y = SRC_Y[name]
        c.wire((110, y), (BUS[name], y))              # trunk
        c.wire((160, y), (160, y + 40), (210, y + 40))   # tap to inverter
        c.wire((240, y + 40), (BUS[name + "_"], y + 40))

    # which rows each signal must reach; buses stop at their last tap
    taps = {k: [] for k in BUS}
    for i, y in enumerate(ys):
        bits = [(i >> 0) & 1, (i >> 1) & 1, (i >> 2) & 1]
        for k, b in enumerate(bits):
            taps[["A", "B", "C"][k] + ("_" if b == 0 else "")].append(y + OFF[k])
    for name, x in BUS.items():
        c.wire((x, SRC_Y[name]), (x, max(taps[name])))
    c.wire((600, 100), (600, ys[-1] + 20))

    # --- decode rows ----------------------------------------------------
    for i, y in enumerate(ys):
        bits = [(i >> 0) & 1, (i >> 1) & 1, (i >> 2) & 1]
        for k, b in enumerate(bits):
            name = ["A", "B", "C"][k] + ("_" if b == 0 else "")
            c.wire((BUS[name], y + OFF[k]), (GX - 60, y + OFF[k]))
        c.wire((600, y + 20), (GX - 60, y + 20))
        c.wire((GX, y), (880, y))
    return c


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "74ls138.circ")
    circuit = build()
    circuit.save(path)
    normalize(path)          # let Logisim re-save it: that is what it expects on disk
    report = verify(path, drivers=circuit.drivers())
    print(json_dump(report.as_dict()))
    if not report.ok:
        return 1
    print("\nG1 G2A G2B | A B C | Y7 Y6 Y5 Y4 Y3 Y2 Y1 Y0   (0 = selected)")
    for g1, g2a, g2b in [(1, 0, 0), (1, 1, 1), (0, 0, 0)]:
        e = (not g1) and (not g2a) and (not g2b)
        for a in (0, 1):
            for b in (0, 1):
                for cc in (0, 1):
                    outs = []
                    for i in range(8):
                        sel = ((i >> 0) & 1) == a and ((i >> 1) & 1) == b and ((i >> 2) & 1) == cc
                        outs.append(0 if (sel and e) else 1)
                    print("%2d %3d %3d | %d %d %d | %s" % (g1, g2a, g2b, cc, b, a,
                          "  ".join(str(o) for o in reversed(outs))))
    return 0


def json_dump(obj):
    import json
    return json.dumps(obj, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
