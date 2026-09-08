#!/usr/bin/env python3
"""Check place-and-route support for SC64's hard cells without programming hardware.

Minimal blackbox declarations preserve EFB and ODDRXE cell names for the
backend capability check; they provide no behavioral substitute. Unconstrained
pins are permitted only in these isolated diagnostic designs.
"""

import argparse
import json
from pathlib import Path
import subprocess


CELLS = {
    "logic": """module top(input clk, input data, output out);
reg [7:0] count = 0;
always @(posedge clk) count <= count + data;
assign out = count[7];
endmodule
""",
    "EFB": """(* blackbox *) module EFB(input WBCLKI, WBCYCI, output WBACKO);
endmodule
module top(input clk, input data, output out);
EFB cell_inst(.WBCLKI(clk), .WBCYCI(data), .WBACKO(out));
endmodule
""",
    "ODDRXE": """(* blackbox *) module ODDRXE(input SCLK, RST, D0, D1, output Q);
endmodule
module top(input clk, input data, output out);
ODDRXE cell_inst(.SCLK(clk), .RST(1'b0), .D0(data), .D1(1'b0), .Q(out));
endmodule
""",
    "FIFO8KB": """module top(input clk, input data, output out);
FIFO8KB cell_inst(.CLKW(clk), .CLKR(clk), .DI0(data), .WE(data),
                 .RE(1'b1), .DO0(out));
endmodule
""",
}


def run(command, log, cwd):
    with log.open("w") as stream:
        return subprocess.run(command, cwd=cwd, stdout=stream,
                              stderr=subprocess.STDOUT).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device")
    parser.add_argument("output", type=Path)
    parser.add_argument("--nextpnr", default="/usr/local/bin/nextpnr-machxo2")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    results = {}
    for name, source in CELLS.items():
        work = output / name
        work.mkdir()
        (work / "top.v").write_text(source)
        synth = run(["yosys", "-p", "read_verilog -lib +/lattice/cells_bb_xo2.v; "
                     "read_verilog top.v; synth_lattice -family xo2 -top top -json top.json"],
                    work / "synthesis.log", work)
        route = None
        if synth == 0:
            route = run([args.nextpnr, "--device", args.device,
                         "--json", "top.json", "--textcfg", "top.config",
                         "--lpf-allow-unconstrained", "--freq", "10"],
                        work / "route.log", work)
        pack = None
        if route == 0:
            pack = run(["ecppack", "--input", "top.config", "--bit", "diagnostic.bit"],
                       work / "pack.log", work)
        results[name] = {"synthesis_exit": synth, "route_exit": route, "pack_exit": pack}
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
    return int(any(r["synthesis_exit"] != 0 or r["route_exit"] != 0 or r["pack_exit"] != 0
                   for r in results.values()))


if __name__ == "__main__":
    raise SystemExit(main())
