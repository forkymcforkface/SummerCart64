#!/usr/bin/env python3
"""Attempt the unchanged Diamond source manifest with the open MachXO2 tools.

This research probe preserves every instantiated primitive and fails on unknown
modules. Its outputs are diagnostic netlists, never deployable firmware.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="SC64 checkout with built CIC")
    parser.add_argument("output", type=Path, help="new diagnostic directory")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    if any(c.isspace() or c in '\";\\' for c in str(root) + str(output)):
        parser.error("mount the checkout and output at simple POSIX paths")
    output.mkdir(parents=True, exist_ok=False)
    project = root / "fw/project/lcmxo2/sc64.ldf"
    tree = ET.parse(project).getroot()
    sources = [
        (project.parent / node.attrib["name"]).resolve()
        for node in tree.findall("Implementation/Source")
        if node.get("type") == "Verilog" and node.get("excluded") != "TRUE"
    ]
    cic = root / "sw/cic/build/cic.mem"
    inputs = sources + [project, project.with_suffix(".lpf"), cic]
    manifest = {
        "device": tree.attrib["device"],
        "inputs": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in inputs},
    }
    (output / "inputs.json").write_text(json.dumps(manifest, indent=2) + "\n")
    commands = [
        "read_verilog -lib +/lattice/cells_sim_xo2.v",
        "read_slang --top top --allow-use-before-declare --error-limit 0 "
        "-I/opt/oss-cad-suite/share/yosys/lattice "
        "/opt/oss-cad-suite/share/yosys/lattice/cells_bb_xo2.v "
        + " ".join(str(p) for p in sources),
        f'synth_lattice -family xo2 -top top -json "{output / "sc64.json"}"',
        "check -assert",
    ]
    script = output / "synth.ys"
    script.write_text("\n".join(commands) + "\n")
    with (output / "synthesis.log").open("w") as log:
        result = subprocess.run(["yosys", "-m", "slang", "-T", "-s", str(script)],
                                cwd=project.parent, stdout=log, stderr=subprocess.STDOUT)
    (output / "status.json").write_text(json.dumps({
        "synthesis_exit": result.returncode,
        "hardware_qualified": False,
        "bitstream_generated": False,
    }, indent=2) + "\n")
    print(f"synthesis_exit={result.returncode} log={output / 'synthesis.log'}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
