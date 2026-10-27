"""Real Logisim vector checks and native state rendering (ITA-compatible)."""
import os, subprocess
from pathlib import Path
from .verify import ensure_dumper, find_java, find_jar, dump, parse

def simulate(path: str, circuit: str, vectors_csv: str, image_path: str = '') -> dict:
    java_out = ensure_dumper()
    env = dict(os.environ, JAVA_TOOL_OPTIONS='-Djava.awt.headless=true -Djava.util.prefs.PreferencesFactory=MemPrefsFactory')
    cmd = [find_java(), '-cp', os.pathsep.join([java_out, find_jar()]), 'SimCheck', str(Path(path).resolve()), circuit, str(Path(vectors_csv).resolve())]
    if image_path: cmd.append(str(Path(image_path).resolve()))
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', env=env, timeout=120)
    rows = p.stdout.splitlines()
    return {'ok': p.returncode == 0, 'circuit': circuit, 'rows': max(0, len(rows)-1), 'actual_csv': p.stdout, 'diagnostics': p.stderr, 'image': image_path if p.returncode == 0 else ''}

def inspect(path: str) -> dict:
    """Circuit-scoped topology inspection; full functional proof uses simulate."""
    raw = dump(path); reports = {}
    for section in raw.split('CIRCUIT ')[1:]:
        name = section.split(' bounds=', 1)[0]
        nl = parse('\n'.join(section.splitlines()[1:])); drivers=[]
        # Infer one-bit gate/pin sources; passive splitters/tunnels are not drivers.
        for co in nl.components:
            if co['name'] not in ('Tunnel','Splitter'):
                drivers.extend((p,co['name']+str(co['loc'])) for p,inn,out in co['ports'] if out and not inn)
        conflicts = nl.multi_driver_nets(drivers)
        dangling = nl.dangling_ends()
        reports[name]={'components':len(nl.components),'wires':len(nl.wires),'dangling':dangling,'local_driver_conflicts':{str(k):v for k,v in conflicts.items()},'ok':not dangling and not conflicts}
    return {'ok':bool(reports) and all(r['ok'] for r in reports.values()),'circuits':reports,'scope':'Per-circuit physical-wire checks. Tunnel equivalence, splitter bit routing, truth tables and driven values require simulate_vectors.'}
