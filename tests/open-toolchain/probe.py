#!/usr/bin/env python3
"""Attempt the unchanged Diamond source manifest with the open MachXO2 tools.

This research probe preserves every instantiated primitive and fails on unknown
modules. Its outputs are diagnostic netlists, never deployable firmware.
"""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import re
import subprocess
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="SC64 checkout with built CIC")
    parser.add_argument("output", type=Path, help="new diagnostic directory")
    parser.add_argument("--primitive", type=Path, action="append", default=[],
                        help="explicit hardware primitive declaration; never an implementation")
    parser.add_argument("--frontend", choices=("slang", "sv2v"), default="slang")
    parser.add_argument("--sv2v", default="sv2v", help="sv2v executable for the opt-in diagnostic frontend")
    parser.add_argument("--timeout", type=int, default=600, help="per-stage process-group timeout in seconds")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    root = args.root.resolve()
    output = args.output.resolve()
    primitives = [p.resolve() for p in args.primitive]
    if any(c.isspace() or c in '\";\\' for c in "".join(map(str, [root, output] + primitives))):
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
        "frontend": args.frontend,
        "inputs": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in inputs},
        "primitive_declarations": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in primitives},
    }
    (output / "inputs.json").write_text(json.dumps(manifest, indent=2) + "\n")
    def run(command, log_path):
        with log_path.open("w") as log:
            try:
                process = subprocess.Popen(command, cwd=project.parent, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
            except OSError as exc:
                log.write(str(exc) + "\n")
                return 127 if isinstance(exc, FileNotFoundError) else 126
            try:
                return process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                return 124

    conversion_exit = None
    if args.frontend == "sv2v":
        try:
            version = subprocess.run([args.sv2v, "--version"], text=True, capture_output=True,
                                     timeout=10, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            code = (124 if isinstance(exc, subprocess.TimeoutExpired) else
                    127 if isinstance(exc, FileNotFoundError) else
                    exc.returncode if isinstance(exc, subprocess.CalledProcessError) else 126)
            (output / "sv2v-version.log").write_text(str(exc) + "\n")
            (output / "status.json").write_text(json.dumps({"frontend": args.frontend,
                "failed_stage": "sv2v-version", "prerequisite_exit": code,
                "conversion_exit": None, "synthesis_exit": None,
                "hardware_qualified": False, "bitstream_generated": False}, indent=2) + "\n")
            print(f"prerequisite_exit={code} log={output / 'sv2v-version.log'}")
            return code
        manifest["sv2v_version"] = version.stdout.strip()
        executable = Path(shutil.which(args.sv2v) or args.sv2v).resolve()
        manifest["sv2v_executable"] = str(executable)
        manifest["sv2v_executable_sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
        generated = output / "converted.v"
        with generated.open("w") as converted, (output / "conversion.log").open("w") as log:
            try:
                process = subprocess.Popen([args.sv2v, "--top=top",
                    "-I/opt/oss-cad-suite/share/yosys/lattice",
                    "/opt/oss-cad-suite/share/yosys/lattice/cells_bb_xo2.v",
                    *map(str, primitives + sources)], cwd=project.parent, stdout=converted,
                    stderr=log, start_new_session=True)
                conversion_exit = process.wait(timeout=args.timeout)
            except OSError as exc:
                log.write(str(exc) + "\n")
                conversion_exit = 127 if isinstance(exc, FileNotFoundError) else 126
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                conversion_exit = 124
        manifest["generated_conversion_sha256"] = hashlib.sha256(generated.read_bytes()).hexdigest()
        (output / "inputs.json").write_text(json.dumps(manifest, indent=2) + "\n")
        if conversion_exit:
            (output / "status.json").write_text(json.dumps({"conversion_exit": conversion_exit,
                "synthesis_exit": None, "hardware_qualified": False, "bitstream_generated": False}, indent=2) + "\n")
            return conversion_exit
        frontend_command = f'read_verilog "{generated}"'
    else:
        frontend_command = (
            "read_slang --top top --allow-use-before-declare --error-limit 0 "
            "-I/opt/oss-cad-suite/share/yosys/lattice "
            "/opt/oss-cad-suite/share/yosys/lattice/cells_bb_xo2.v "
            + " ".join(str(p) for p in primitives + sources))
    commands = [
        "read_verilog -lib +/lattice/cells_sim_xo2.v",
        frontend_command,
        f'synth_lattice -family xo2 -top top -json "{output / "sc64.json"}"',
        "check -assert",
    ]
    script = output / "synth.ys"
    script.write_text("\n".join(commands) + "\n")
    code = run(["yosys", "-m", "slang", "-T", "-s", str(script)], output / "synthesis.log")
    if code == 0:
        netlist = json.loads((output / "sc64.json").read_text())
        cells = netlist["modules"]["top"]["cells"]
        summary = {
            "cell_counts": dict(Counter(c["type"] for c in cells.values())),
            "register_mapped_memories": re.findall(r"using FF mapping for memory (.+)",
                (output / "synthesis.log").read_text()),
            "n64_video_sync_bits": netlist["modules"]["top"]["ports"]["n64_video_sync"]["bits"],
            "fit_verified": False,
            "cic_initialization_bit_order_verified": False,
        }
        (output / "mapping-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "status.json").write_text(json.dumps({
        "frontend": args.frontend,
        "conversion_exit": conversion_exit,
        "synthesis_exit": code,
        "hardware_qualified": False,
        "bitstream_generated": False,
    }, indent=2) + "\n")
    print(f"synthesis_exit={code} log={output / 'synthesis.log'}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
