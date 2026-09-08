"""Map a supplied sv2v SC64 conversion using guarded old-data RAM forwarding.

The caller supplies the unchanged-manifest conversion and project working
folder containing the CIC path. This is not a production synthesis entry point.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from forward import transform


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("converted", type=Path)
    parser.add_argument("project_directory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    converted = args.converted.resolve()
    project = args.project_directory.resolve()
    out = args.output.resolve()
    for path in (converted, project, out):
        if any(c.isspace() or c in '";\\' for c in str(path)):
            parser.error("use simple POSIX paths")
    out.mkdir(parents=True, exist_ok=False)
    result = {
        "status": "running",
        "converted_sha256": hashlib.sha256(converted.read_bytes()).hexdigest(),
        "physical_qualification": False,
    }
    status = out / "result.json"

    def run(name, commands):
        script = out / (name + ".ys")
        script.write_text(commands)
        with (out / (name + ".log")).open("w") as log:
            subprocess.run(
                ["yosys", "-Q", "-T", "-s", str(script)],
                cwd=project,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=600,
                check=True,
            )

    prepare = f"read_verilog -lib +/lattice/cells_sim_xo2.v\nread_verilog {converted}\nsynth_lattice -family xo2 -top top -run begin:map_ram\n"
    try:
        run(
            "prepare",
            prepare + f"select top\nwrite_json -selected {out}/original.json\n",
        )
        design = json.loads((out / "original.json").read_text())
        names = [
            "memory_bram_inst.dd_bram",
            "memory_bram_inst.eeprom_bram_high",
            "memory_bram_inst.eeprom_bram_low",
            "mcu_top_inst.mem_buffer",
        ]
        if not all(n in design["modules"]["top"]["cells"] for n in names):
            raise ValueError("expected exact four SC64 memory instances missing")
        gate = transform(design, "top", names, out / "address-proof")
        (out / "forward.json").write_text(json.dumps(gate))
        run(
            "map",
            prepare
            + f"delete top\nread_json {out}/forward.json\nsynth_lattice -family xo2 -top top -run map_ram:map_ffram\nselect top\nwrite_json -selected {out}/mapped-ram.json\nselect -clear\nsynth_lattice -family xo2 -top top -run map_ffram:\ncheck -assert\nwrite_json {out}/mapped.json\nstat\n",
        )
        ramcells = json.loads((out / "mapped-ram.json").read_text())["modules"]["top"][
            "cells"
        ]
        checked = 0
        for name in names:
            blocks = [
                c
                for n, c in ramcells.items()
                if n.startswith(name + ".") and c["type"] == "DP8KC"
            ]
            if not blocks:
                raise ValueError("target memory did not map to DP8KC: " + name)
            for block in blocks:
                for port, suffix in (("A", "a"), ("B", "b")):
                    expected = ramcells[name + "$repair$read_" + suffix]["connections"][
                        "Y"
                    ]
                    if (
                        block["connections"]["CE" + port] != expected
                        or block["parameters"]["WRITEMODE_" + port] != "READBEFOREWRITE"
                    ):
                        raise ValueError("physical port enable/mode mismatch: " + name)
                checked += 1
        mapped = json.loads((out / "mapped.json").read_text())["modules"]["top"]
        counts = Counter(c["type"] for c in mapped["cells"].values())
        if any(c["type"] == "$mem_v2" for c in mapped["cells"].values()):
            raise ValueError("unmapped memory remains")
        result.update(
            status="passed",
            cells=dict(sorted(counts.items())),
            address_implications=8,
            guarded_physical_blocks=checked,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result.update(status="failed", error=str(exc))
        raise
    finally:
        status.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
