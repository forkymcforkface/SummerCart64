"""Reproduce generic forwarding proof, collision poisoning, and its negative control."""

import argparse
import copy
import json
from pathlib import Path
import subprocess
from forward import transform
from address_proof import prove_addresses


def yosys(output, name, commands, expect=0):
    script = output / (name + ".ys")
    script.write_text(commands)
    with (output / (name + ".log")).open("w") as log:
        result = subprocess.run(
            ["yosys", "-Q", "-T", "-s", str(script)],
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=120,
        )
    if (result.returncode == 0) != (expect == 0):
        raise RuntimeError(f"{name}: unexpected exit {result.returncode}")


def poison(design):
    m = design["modules"]["dual_enabled"]
    cells = m["cells"]
    q = cells["mem"]["connections"]
    raw = q["RD_DATA"]
    first = (
        max(
            b
            for c in cells.values()
            for v in c["connections"].values()
            for b in v
            if isinstance(b, int)
        )
        + 1
    )
    q["RD_DATA"] = list(range(first, first + 6))
    for i in range(2):
        arbitrary = list(range(first + 6 + i * 3, first + 9 + i * 3))
        cells["poison" + str(i)] = {
            "type": "$anyseq",
            "parameters": {"WIDTH": 3},
            "attributes": {},
            "port_directions": {"Y": "output"},
            "connections": {"Y": arbitrary},
        }
        cells["poisonmux" + str(i)] = {
            "type": "$mux",
            "parameters": {"WIDTH": 3},
            "attributes": {},
            "port_directions": {
                "A": "input",
                "B": "input",
                "S": "input",
                "Y": "output",
            },
            "connections": {
                "A": q["RD_DATA"][i * 3 : (i + 1) * 3],
                "B": arbitrary,
                "S": cells["mem$repair$select" + str(i)]["connections"]["Q"],
                "Y": raw[i * 3 : (i + 1) * 3],
            },
        }
    return design


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent
    yosys(
        out,
        "prepare",
        f"read_verilog {here}/dual_enabled.v\nsynth_lattice -family xo2 -top dual_enabled -run begin:map_ram\nselect dual_enabled\nwrite_json -selected {out}/gold.json\n",
    )
    gold = json.loads((out / "gold.json").read_text())
    prove_addresses(gold, "dual_enabled", ["mem"], out / "addresses")
    gate = transform(
        copy.deepcopy(gold), "dual_enabled", ["mem"], out / "transform-addresses"
    )
    (out / "gate.json").write_text(json.dumps(gate))
    arbitrary = poison(copy.deepcopy(gate))
    (out / "arbitrary.json").write_text(json.dumps(arbitrary))
    negative = copy.deepcopy(arbitrary)
    q = negative["modules"]["dual_enabled"]["cells"]["mem$repair$data0"]["connections"]
    q["B"] = q["A"]
    (out / "negative.json").write_text(json.dumps(negative))
    for name in ("gate", "arbitrary", "negative"):
        commands = f"""read_json {out}/gold.json
memory_map
opt_clean
rename dual_enabled gold
design -stash gold
read_json {out}/{name}.json
memory_map
opt_clean
rename dual_enabled gate
design -stash gate
design -copy-from gold -as gold gold
design -copy-from gate -as gate gate
equiv_make gold gate equiv
hierarchy -top equiv
equiv_simple -undef
equiv_induct -seq 5
equiv_status -assert
"""
        yosys(out, name + "-proof", commands, expect=1 if name == "negative" else 0)
    yosys(
        out,
        "map",
        f"read_json {out}/gate.json\nsynth_lattice -family xo2 -top dual_enabled -run map_ram:map_ffram\nstat\n",
    )
    yosys(
        out,
        "large-prepare",
        f"read_verilog {here}/dual_old.v\nsynth_lattice -family xo2 -top dual_old -run begin:map_ram\nselect dual_old\nwrite_json -selected {out}/large.json\n",
    )
    large = transform(
        json.loads((out / "large.json").read_text()),
        "dual_old",
        ["mem"],
        out / "large-addresses",
    )
    (out / "large-gate.json").write_text(json.dumps(large))
    yosys(
        out,
        "large-map",
        f"read_json {out}/large-gate.json\nsynth_lattice -family xo2 -top dual_old -run map_ram:map_ffram\nwrite_json {out}/large-mapped.json\nstat\n",
    )
    cells = json.loads((out / "large-mapped.json").read_text())["modules"]["dual_old"][
        "cells"
    ]
    rams = [c for c in cells.values() if c["type"] == "DP8KC"]
    if len(rams) != 2:
        raise RuntimeError("large fixture did not map to exactly two DP8KC")
    for ram in rams:
        for port, suffix in (("A", "a"), ("B", "b")):
            if (
                ram["connections"]["CE" + port]
                != cells["mem$repair$read_" + suffix]["connections"]["Y"]
            ):
                raise RuntimeError("physical CE is not the guarded read enable")
            if ram["parameters"]["WRITEMODE_" + port] != "READBEFOREWRITE":
                raise RuntimeError("physical port does not preserve same-port old data")
    broken = copy.deepcopy(gold)
    broken["modules"]["dual_enabled"]["cells"]["mem"]["connections"]["WR_ADDR"] = [
        "0"
    ] * 4
    try:
        transform(broken, "dual_enabled", ["mem"], out / "bad-addresses")
    except subprocess.CalledProcessError:
        pass
    else:
        raise RuntimeError("wrong enabled write address was accepted")
    result = {
        "generic_equivalence": True,
        "arbitrary_collision_equivalence": True,
        "broken_forwarding_rejected": True,
        "physical_ce_mapping": True,
        "wrong_address_rejected": True,
        "physical_qualification": False,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
