"""Read a .circ back with Logisim's own loader and analyse the netlist.

Writing XML is not enough: a file can be well-formed, load without errors and
still be electrically wrong (wires one grid unit short, two drivers shorted
together, wires hanging in the air).  The only trustworthy check is to let
Logisim parse it and then reason about the geometry.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
JAVA_SRC = os.path.join(os.path.dirname(HERE), "tools", "java")
JAVA_OUT = os.path.join(JAVA_SRC, "out")

COMP_RE = re.compile(r"\s{2}(.+?) loc=\((\d+),(\d+)\) bounds")
PORT_RE = re.compile(r"\s+port \((\d+),(\d+)\) .*in=(\w+) out=(\w+)")
WIRE_RE = re.compile(r"\s+WIRE \((\d+),(\d+)\) -> \((\d+),(\d+)\)")


def find_java() -> str:
    for cand in (os.environ.get("JAVA"), shutil.which("java")):
        if cand and os.path.exists(cand):
            return cand
    home = os.environ.get("JAVA_HOME")
    if home:
        exe = os.path.join(home, "bin", "java.exe" if os.name == "nt" else "java")
        if os.path.exists(exe):
            return exe
    raise RuntimeError("no java found; set JAVA or JAVA_HOME")


def find_jar() -> str:
    for cand in (os.environ.get("LOGISIM_JAR"),
                 r"E:\Logisim\Logisim-ITA.exe",
                 "/usr/share/logisim/logisim.jar"):
        if cand and os.path.exists(cand):
            return cand
    raise RuntimeError("no Logisim jar found; set LOGISIM_JAR to your logisim jar/exe")


def ensure_dumper() -> None:
    """Compile tools/java/*.java against the Logisim jar (once)."""
    if os.path.exists(os.path.join(JAVA_OUT, "LoadDump.class")):
        return
    javac = os.path.join(os.path.dirname(find_java()),
                         "javac.exe" if os.name == "nt" else "javac")
    os.makedirs(JAVA_OUT, exist_ok=True)
    srcs = [os.path.join(JAVA_SRC, f) for f in os.listdir(JAVA_SRC) if f.endswith(".java")]
    subprocess.run([javac, "-cp", find_jar(), "-d", JAVA_OUT] + srcs, check=True)


def dump(circ_path: str) -> str:
    ensure_dumper()
    env = dict(os.environ)
    # Logisim writes java.util.prefs to the registry, which fails inside
    # sandboxes / CI; MemPrefsFactory keeps them in memory instead.
    env["JAVA_TOOL_OPTIONS"] = (
        "-Djava.awt.headless=true -Djava.util.prefs.PreferencesFactory=MemPrefsFactory")
    cp = os.pathsep.join([find_jar(), JAVA_OUT])
    res = subprocess.run([find_java(), "-Xmx1g", "-cp", cp, "LoadDump", circ_path],
                         capture_output=True, text=True, encoding="utf-8", env=env)
    out = res.stdout
    if "LOADER ERROR" in out:
        errs = [l for l in out.splitlines() if "ERROR" in l]
        raise RuntimeError("Logisim rejected the file:\n" + "\n".join(errs))
    return out


@dataclass
class Netlist:
    components: list = field(default_factory=list)   # [{name, loc, ports:[(p, in, out)]}]
    wires: list = field(default_factory=list)        # [((x,y),(x,y))]
    parent: dict = field(default_factory=dict)

    # -- union find -------------------------------------------------------
    def find(self, p):
        self.parent.setdefault(p, p)
        while self.parent[p] != p:
            self.parent[p] = self.parent[self.parent[p]]
            p = self.parent[p]
        return p

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def net(self, p):
        return self.find(p)

    # -- geometry ---------------------------------------------------------
    @staticmethod
    def on_segment(p, a, b) -> bool:
        if a[0] == b[0] == p[0]:
            return min(a[1], b[1]) < p[1] < max(a[1], b[1])
        if a[1] == b[1] == p[1]:
            return min(a[0], b[0]) < p[0] < max(a[0], b[0])
        return False

    def build(self):
        for a, b in self.wires:
            self.union(a, b)
        points = [p for c in self.components for p, _, _ in c["ports"]]
        for p in points:
            for a, b in self.wires:
                if self.on_segment(p, a, b):
                    self.union(p, a)
        return self

    def ports(self):
        return [(p, c["name"], inn, out) for c in self.components for p, inn, out in c["ports"]]

    def nets(self):
        groups = defaultdict(lambda: {"points": set(), "ports": []})
        for a, b in self.wires:
            for p in (a, b):
                groups[self.find(p)]["points"].add(p)
        for p, name, inn, out in self.ports():
            groups[self.find(p)]["ports"].append((name, inn, out))
        return groups

    def dangling_ends(self):
        """Wire ends that touch nothing: the "broken wire" look."""
        ends = defaultdict(int)
        for a, b in self.wires:
            ends[a] += 1
            ends[b] += 1
        portset = {p for p, _, _, _ in self.ports()}
        bad = []
        for p, n in ends.items():
            if p in portset or n > 1:
                continue
            if any(self.on_segment(p, a, b) for a, b in self.wires if p not in (a, b)):
                continue
            bad.append(p)
        return sorted(bad)

    def multi_driver_nets(self, drivers):
        """Nets with more than one driver -> Logisim paints them red."""
        by_net = defaultdict(list)
        for p, tag in drivers:
            by_net[self.find(p)].append(tag)
        return {k: v for k, v in by_net.items() if len(v) > 1}


def parse(text: str) -> Netlist:
    nl = Netlist()
    cur = None
    for line in text.splitlines():
        m = COMP_RE.match(line)
        if m:
            cur = {"name": m.group(1).strip(),
                   "loc": (int(m.group(2)), int(m.group(3))), "ports": []}
            nl.components.append(cur)
            continue
        m = PORT_RE.match(line)
        if m and cur is not None:
            cur["ports"].append(((int(m.group(1)), int(m.group(2))),
                                 m.group(3) == "true", m.group(4) == "true"))
            continue
        m = WIRE_RE.match(line)
        if m:
            g = [int(x) for x in m.groups()]
            nl.wires.append(((g[0], g[1]), (g[2], g[3])))
    return nl.build()


@dataclass
class Report:
    components: int
    wires: int
    nets: int
    dangling: list
    conflicts: dict
    ok: bool

    def as_dict(self):
        return {
            "components": self.components,
            "wires": self.wires,
            "nets": self.nets,
            "dangling": [list(p) for p in self.dangling],
            "conflicts": {str(k): v for k, v in self.conflicts.items()},
            "ok": self.ok,
        }


def verify(circ_path: str, drivers=None) -> Report:
    nl = parse(dump(circ_path))
    dangling = nl.dangling_ends()
    conflicts = nl.multi_driver_nets(drivers or [])
    return Report(len(nl.components), len(nl.wires), len(nl.nets()),
                  dangling, conflicts, not dangling and not conflicts)
