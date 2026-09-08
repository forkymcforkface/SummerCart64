"""Remap one guarded synchronous-reset FF and test its physical consequence.

The runner accepts only the passed compact checkpoint, records local induction
evidence, and checks the selected transformation and packed outcome. It emits
no placement, routing or hardware image.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


TARGET_NET = "n64_scb.flashram_done"
EXPECTED_CHECKPOINT = "2e7b66affe6937a0a5a8520a24a74d69f60c4454b15f7dfa3e28840e560c2c84"
EXPECTED_AREA_RESULT = "0ebe1015682c133324b61e2edd83092cd2580dca2f0b84522f068e2b46b23075"
EXPECTED_NEXTPNR = "c6fac50f2c98a7f94aadaffa29793900e8d1e5965b3905b8097274f749e9e607"
EXPECTED_LPF = "cea5c416f963c8302b33af7c2a02ba60a951b60cc0628f486da3351320b3369e"
EXPECTED_YOSYS = "7c3e3396b38c129dd7485be5a0a0f0da8e495a94c8fd486059e3bea043a588d6"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log, timeout=600, check=True):
    with log.open("w") as stream:
        try:
            completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                       timeout=timeout)
            code = completed.returncode
        except subprocess.TimeoutExpired:
            code = 124
    if check and code:
        raise RuntimeError(f"command failed ({code}): {log.name}")
    return code


def module_for_cell(cell, q_attributes):
    ports = {}
    netnames = {}
    connections = {}
    bit = 2
    for port in ["CLK", "D", "SRST", "Q"]:
        ports[port] = {"direction": "output" if port == "Q" else "input", "bits": [bit]}
        netnames[port] = {"hide_name": 0, "bits": [bit],
                          "attributes": q_attributes if port == "Q" else {}}
        connections[port] = [bit]
        bit += 1
    return {"attributes": {"top": "1"}, "ports": ports,
            "cells": {"subject": {**cell, "connections": connections}},
            "netnames": netnames}


def check_scope(before, after, name):
    """Compare circuit identity across JSON's independently numbered net bits."""
    bits = {}
    for net, value in before["netnames"].items():
        other = after["netnames"].get(net)
        if other is None or len(value["bits"]) != len(other["bits"]):
            raise ValueError("reset unmap changed an existing net")
        for old, new in zip(value["bits"], other["bits"]):
            if isinstance(old, str):
                if old != new:
                    raise ValueError("reset unmap changed a constant")
            elif old in bits and bits[old] != new:
                raise ValueError("reset unmap changed a net alias")
            else:
                bits[old] = new
    if any(not isinstance(b, int) for b in bits.values()) or len(set(bits.values())) != len(bits):
        raise ValueError("reset unmap merged an existing net or tied it constant")
    before = json.loads(json.dumps(before))
    def mapped(values):
        return [bits[b] if isinstance(b, int) else b for b in values]
    for value in [*before["ports"].values(), *before["netnames"].values()]:
        value["bits"] = mapped(value["bits"])
    for cell in before["cells"].values():
        cell["connections"] = {p: mapped(v) for p, v in cell["connections"].items()}
    unchanged = {n: c for n, c in before["cells"].items() if n != name}
    if any(after["cells"].get(n) != c for n, c in unchanged.items()):
        raise ValueError("reset unmap changed an unrelated cell")
    changed = [c for n, c in after["cells"].items() if n not in unchanged]
    if Counter(c["type"] for c in changed) != {"$dff": 1, "$mux": 1}:
        raise ValueError("reset unmap is not one DFF and one mux")
    ff = next(c for c in changed if c["type"] == "$dff")
    for port in ["CLK", "Q"]:
        if ff["connections"][port] != before["cells"][name]["connections"][port]:
            raise ValueError("reset unmap changed clock or state identity")
    if before["ports"] != after["ports"]:
        raise ValueError("reset unmap changed module ports")
    for net, value in before["netnames"].items():
        if after["netnames"].get(net) != value:
            raise ValueError("reset unmap changed an existing net or initialization")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["checkpoint", "area-result", "project", "executable", "lpf", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists() or out.is_relative_to(Path(__file__).resolve().parents[2]):
        parser.error("fresh output outside tests required")
    checkpoint = args.checkpoint.resolve()
    area_result = args.area_result.resolve()
    executable = args.executable.resolve()
    lpf = args.lpf.resolve()
    expected = {checkpoint: EXPECTED_CHECKPOINT, area_result: EXPECTED_AREA_RESULT,
                executable: EXPECTED_NEXTPNR, lpf: EXPECTED_LPF}
    yosys = Path(shutil.which("yosys"))
    if digest(yosys) != EXPECTED_YOSYS:
        parser.error("pinned Yosys hash mismatch")
    hashes = {str(path): digest(path) for path in [*expected, yosys, Path(__file__).resolve()]}
    if any(hashes[str(path)] != value for path, value in expected.items()):
        parser.error("pinned input hash mismatch")
    prior = json.loads(area_result.read_text())
    recorded = [value for path, value in prior.get("source_hashes", {}).items()
                if Path(path).name == "forward.json"]
    if prior.get("status") != "pass" or recorded != [EXPECTED_CHECKPOINT]:
        parser.error("checkpoint lacks unique passed compact-area provenance")

    out.mkdir(parents=True)
    os.chdir(args.project.resolve())
    result = {"status": "running", "hardware_qualified": False,
              "whole_design_equivalence_proven": False, "target_net": TARGET_NET,
              "source_hashes": hashes}
    try:
        source = json.loads(checkpoint.read_text())
        top = source["modules"]["top"]
        target_bits = top["netnames"][TARGET_NET]["bits"]
        drivers = [(name, cell) for name, cell in top["cells"].items()
                   if cell.get("connections", {}).get("Q") == target_bits]
        if len(drivers) != 1:
            raise ValueError("target does not have exactly one Q driver")
        cell_name, cell = drivers[0]
        if cell["type"] != "$sdff" or cell["parameters"] != {
                "CLK_POLARITY": "00000000000000000000000000000001",
                "SRST_POLARITY": "00000000000000000000000000000001",
                "SRST_VALUE": "0", "WIDTH": "00000000000000000000000000000001"}:
            raise ValueError("target driver is not the expected synchronous-reset cell")
        q_names = [net for net in top["netnames"].values() if net["bits"] == target_bits]
        q_attributes = q_names[0].get("attributes", {})
        if len(q_names) != 1:
            raise ValueError("target Q net identity is ambiguous")
        original = {"modules": {"top": module_for_cell(cell, q_attributes)}}
        (out / "original-cell.json").write_text(json.dumps(original))

        remap_script = (f"read_json {out}/original-cell.json\n"
                        "select top/subject\n"
                        "dffunmap -srst-only\n"
                        "select -clear\ncheck -assert\n"
                        f"write_json {out}/remapped-cell.json\n")
        (out / "cell-remap.ys").write_text(remap_script)
        run(["yosys", "-Q", "-T", "-s", str(out / "cell-remap.ys")], out / "cell-remap.log")
        remapped = json.loads((out / "remapped-cell.json").read_text())["modules"]["top"]
        q_drivers = [(name, item) for name, item in remapped["cells"].items()
                     if item.get("connections", {}).get("Q") == [5]]
        if len(q_drivers) != 1 or q_drivers[0][1]["type"] not in ("$dff", "$_DFF_P_"):
            raise ValueError("dffunmap did not leave one plain DFF driver")
        if remapped["netnames"]["Q"].get("attributes", {}) != q_attributes:
            raise ValueError("Q startup attributes changed")

        proof_script = (f"read_json {out}/original-cell.json\nrename top original\n"
                        f"read_json {out}/remapped-cell.json\nrename top remapped\n"
                        "equiv_make original remapped equiv\nhierarchy -top equiv\n"
                        "equiv_induct -undef -seq 2\nequiv_status -assert\n")
        (out / "proof.ys").write_text(proof_script)
        run(["yosys", "-Q", "-T", "-s", str(out / "proof.ys")], out / "proof.log", 180)
        proof_text = (out / "proof.log").read_text()
        if "Equivalence successfully proven" not in proof_text:
            raise ValueError("positive proof lacks explicit success")
        negative = json.loads((out / "original-cell.json").read_text())
        negative["modules"]["top"]["cells"]["subject"]["parameters"]["SRST_POLARITY"] = \
            "00000000000000000000000000000000"
        (out / "negative-cell.json").write_text(json.dumps(negative))
        negative_script = proof_script.replace("original-cell.json", "negative-cell.json")
        (out / "negative-proof.ys").write_text(negative_script)
        negative_code = run(["yosys", "-Q", "-T", "-s", str(out / "negative-proof.ys")],
                            out / "negative-proof.log", 180, False)
        negative_text = (out / "negative-proof.log").read_text()
        if negative_code == 0 or "0 are proven and 1 are unproven" not in negative_text:
            raise ValueError("negative reset-polarity mutation did not fail the proof")
        result.update(local_induction_passed=True, reset_polarity_negative_rejected=True,
                      next_state_sat_proven=False)

        (out / "forward.json").write_bytes(checkpoint.read_bytes())
        converted = next(Path(path) for path in prior["source_hashes"] if Path(path).name == "converted.v")
        if digest(converted) != prior["source_hashes"][str(converted)]:
            raise ValueError("converted source differs from passed compact provenance")
        hashes[str(converted)] = digest(converted)
        prefix = ("read_verilog -lib +/lattice/cells_sim_xo2.v\n"
                  f"read_verilog {converted}\n"
                  "synth_lattice -family xo2 -top top -run begin:map_ram\n"
                  f"delete top\nread_json {out}/forward.json\n"
                  "synth_lattice -family xo2 -top top -run map_ram:map_ffram\n"
                  f"select top\nwrite_json -selected {out}/mapped-ram.json\nselect -clear\n")
        baseline_script = (prefix +
                           "synth_lattice -family xo2 -top top -noccu2 -run map_ffram:\n"
                           f"check -assert\nwrite_json {out}/baseline-mapped.json\nstat\n")
        (out / "baseline-map.ys").write_text(baseline_script)
        run(["yosys", "-Q", "-T", "-s", str(out / "baseline-map.ys")], out / "baseline-map.log")
        selected_name = "top/\\" + cell_name
        scope_script = (prefix + f"select {selected_name}\n"
                        f"select -assert-count 1 {selected_name}\n"
                        "dffunmap -srst-only\nselect top\n"
                        f"write_json -selected {out}/after-unmap.json\n")
        (out / "scope.ys").write_text(scope_script)
        run(["yosys", "-Q", "-T", "-s", str(out / "scope.ys")], out / "scope.log")
        before = json.loads((out / "mapped-ram.json").read_text())["modules"]["top"]
        after = json.loads((out / "after-unmap.json").read_text())["modules"]["top"]
        check_scope(before, after, cell_name)
        mutated = json.loads(json.dumps(after))
        unrelated = next(n for n in before["cells"] if n != cell_name)
        mutated["cells"][unrelated]["type"] = "$scope_fault"
        try:
            check_scope(before, mutated, cell_name)
        except ValueError as exc:
            if str(exc) != "reset unmap changed an unrelated cell":
                raise
        else:
            raise ValueError("unrelated-cell negative passed")
        result.update(scope_checked=True, scope_negative_rejected=True)
        map_script = (prefix +
                      f"select {selected_name}\n"
                      f"select -assert-count 1 {selected_name}\n"
                      "dffunmap -srst-only\nselect *\n"
                      "synth_lattice -family xo2 -top top -noccu2 -run map_ffram:\n"
                      f"check -assert\nwrite_json {out}/mapped.json\nstat\n")
        (out / "map.ys").write_text(map_script)
        run(["yosys", "-Q", "-T", "-s", str(out / "map.ys")], out / "map.log")
        mapped = json.loads((out / "mapped.json").read_text())["modules"]["top"]
        mapped_counts = dict(Counter(item["type"] for item in mapped["cells"].values()))
        baseline_counts = prior["variants"]["soft-carry"]["cells"]
        ram_types = {"DP8KC", "FIFO8KB", "TRELLIS_DPR16X4"}
        ram_shape = lambda cells: sorted((c["type"], json.dumps(c["parameters"], sort_keys=True))
                                         for c in cells.values() if c["type"] in ram_types)
        baseline_mapped = json.loads((out / "baseline-mapped.json").read_text())["modules"]["top"]
        baseline_fresh_counts = dict(Counter(item["type"] for item in baseline_mapped["cells"].values()))
        if baseline_fresh_counts != baseline_counts:
            raise ValueError("fresh paired baseline mapping differs from passed compact result")
        if ram_shape(mapped["cells"]) != ram_shape(baseline_mapped["cells"]):
            raise ValueError("physical RAM shape or parameters changed")
        if mapped_counts.get("LUT4", 0) + 6 * mapped_counts.get("TRELLIS_DPR16X4", 0) > 6864:
            raise ValueError("targeted reset remap exceeds physical logic capacity")

        prepare = Path("/repo/vendor/sc64/tests/open-toolchain/efb/inactive/prepare.py")
        pll = Path("/repo/vendor/sc64/tests/open-toolchain/oddr/preserve_pll_metadata.py")
        for helper in [prepare, pll]:
            hashes[str(helper)] = digest(helper)
        run(["/usr/bin/python3", "-B", str(prepare), str(out / "mapped.json"),
             str(out / "efb.json"), "--diagnostic"], out / "efb.log")
        pll_source = Path("/repo/build/sc64-open-release/source/fw/rtl/vendor/lcmxo2/generated/pll_lattice_generated.v")
        hashes[str(pll_source)] = digest(pll_source)
        run(["/usr/bin/python3", "-B", str(pll), str(pll_source), str(out / "efb.json"),
             str(out / "physical.json"), str(out / "pll.json")], out / "pll.log")
        pack_command = [str(executable), "--device", "LCMXO2-7000HC-6TG144C",
                        "--json", str(out / "physical.json"), "--lpf", str(lpf), "--pack-only",
                        "--oddr-diagnostic", "--efb-routing-diagnostic", "--fifo-routing-diagnostic",
                        "--write", str(out / "packed.json")]
        run(pack_command, out / "pack.log")
        packed = json.loads((out / "packed.json").read_text())["modules"]["top"]
        packed_target = [(name, item) for name, item in packed["cells"].items()
                         if name == TARGET_NET + "_TRELLIS_FF_Q"]
        if len(packed_target) != 1:
            raise ValueError("packed target FF is not unique")
        target = packed_target[0][1]
        if "DI" not in target["connections"] or target["parameters"].get("SD", "").strip() != "1" \
                or "LSR" in target["connections"]:
            result.update(mapping_outcome="rejected: synchronous reset returned before packing",
                          mapped_cells=mapped_counts, baseline_mapped_cells=baseline_counts,
                          mapped_lut_delta=mapped_counts.get("LUT4", 0)-baseline_counts.get("LUT4", 0),
                          packed_cells=dict(Counter(c["type"] for c in packed["cells"].values())),
                          packed_target={"name": packed_target[0][0],
                                         "parameters": target["parameters"],
                                         "connections": target["connections"]},
                          placement_performed=False)
            raise ValueError("packed target did not become a LUT-fed SD=1 FF without LSR")
        raise ValueError("unexpected improvement needs a separate qualified experiment")
    except Exception as exc:
        result.update(status="failed", error=str(exc))
        raise
    finally:
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
