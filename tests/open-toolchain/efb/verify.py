#!/usr/bin/env python3
"""Verify EFB pin declarations, physical routing, and both firmware barriers.

The original SC64 wrapper is an additional diagnostic, never a claimed hardware
pass. Configuration-bit and timing gaps remain recorded even after routing.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def run(command, work, name):
    with (work / f"{name}.log").open("w") as log:
        return subprocess.run(command, cwd=work, stdout=log,
                              stderr=subprocess.STDOUT, timeout=120).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("nextpnr")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    wrapper = args.root.resolve() / "fw/rtl/vendor/lcmxo2/generated/efb_lattice_generated.v"
    declaration = output / "efb.v"
    subprocess.run([sys.executable, str(Path(__file__).with_name("declaration.py")),
                    str(wrapper), str(declaration)], check=True)
    ports = dict((name, direction) for direction, name in
                 re.findall(r"\b(input|output) (\w+);", declaration.read_text()))
    sys.path.insert(0, "/usr/local/lib/trellis")
    import pytrellis
    pytrellis.load_database("/src/prjtrellis/database")
    graph = pytrellis.Chip("LCMXO2-7000HC").get_routing_graph(False, False)
    bels = [bel for tile in graph.tiles.values() for bel in tile.bels.values()
            if graph.to_str(bel.type) == "EFB"]
    assert len(bels) == 1
    pins = {graph.to_str(pin): "output" if value[1] == pytrellis.PortDirection.PORT_OUT
            else "input" for pin, value in bels[0].pins.items()}
    assert ports == pins, (ports.keys() - pins.keys(), pins.keys() - ports.keys())
    (output / "pin-manifest.json").write_text(json.dumps({
        "wrapper_sha256": hashlib.sha256(wrapper.read_bytes()).hexdigest(),
        "ports": ports,
    }, indent=2) + "\n")
    (output / "top.v").write_text("""module top(input clk, input data, output out);
EFB cell_inst(.WBCLKI(clk), .WBCYCI(data), .WBACKO(out));
endmodule
""")
    synth = "read_verilog efb.v top.v; synth_lattice -family xo2 -top top -json top.json"
    assert run(["yosys", "-p", synth], output, "synthesis") == 0
    route = [args.nextpnr, "--device", "LCMXO2-7000HC-6TG144C", "--json", "top.json",
             "--lpf-allow-unconstrained"]
    normal = run(route, output, "normal")
    assert normal != 0 and "firmware builds are disabled" in (output / "normal.log").read_text()
    diagnostic = route + ["--efb-routing-diagnostic"]
    assert run(diagnostic + ["--write", "routed.json"], output, "routing") == 0
    cell = json.loads((output / "routed.json").read_text())["modules"]["top"]["cells"]["cell_inst"]
    assert cell["type"] == "EFB" and cell["attributes"]["NEXTPNR_BEL"] == "X3/Y1/EFB"
    emission = run(diagnostic + ["--textcfg", "forbidden.config"], output, "emission")
    assert emission != 0 and "configuration bits are unmapped" in (output / "emission.log").read_text()
    assert not (output / "forbidden.config").exists()
    unplaced = run(diagnostic + ["--no-place", "--no-route", "--textcfg", "unplaced.config"],
                   output, "unplaced-emission")
    assert unplaced != 0 and "configuration bits are unmapped" in (output / "unplaced-emission.log").read_text()
    assert not (output / "unplaced.config").exists()
    replay = run([args.nextpnr, "--device", "LCMXO2-7000HC-6TG144C", "--json", "routed.json",
                  "--lpf-allow-unconstrained"], output, "saved-setting")
    assert replay != 0 and "firmware builds are disabled" in (output / "saved-setting.log").read_text()
    (output / "wrapper.v").write_text(wrapper.read_text())
    synth = ("read_verilog -lib +/lattice/cells_sim_xo2.v; read_verilog efb.v wrapper.v; "
             "synth_lattice -family xo2 -top efb_lattice_generated -json wrapper.json")
    assert run(["yosys", "-p", synth], output, "wrapper-synthesis") == 0
    exact = run([args.nextpnr, "--device", "LCMXO2-7000HC-6TG144C", "--json", "wrapper.json",
                 "--lpf-allow-unconstrained", "--efb-routing-diagnostic", "--write", "wrapper-routed.json"],
                output, "wrapper-route")
    result = {"pin_directions_checked": len(ports), "minimal_routing": "pass",
              "normal_build_barrier": "pass", "bitstream_barrier": "pass",
              "unplaced_bitstream_barrier": "pass", "saved_setting_barrier": "pass",
              "original_wrapper_route_exit": exact, "hardware_qualified": False}
    (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
