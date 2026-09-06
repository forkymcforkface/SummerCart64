#!/usr/bin/env python3
"""Derive an EFB interface declaration from SC64's checked-in generated wrapper.

Only ports and explicit parameter values are emitted. This supplies no hardware
implementation; the nextpnr EFB diagnostic prohibits bitstream generation.
"""

from pathlib import Path
import re
import sys


source = Path(sys.argv[1]).read_text()
outputs = set(re.findall(r"output wire\s+(?:\[[^]]+\]\s+)?(\w+)\s*;", source))
instance = re.search(r"\bEFB\s+EFBInst_0\s*\((.*?)\);", source, re.S)
if not instance or outputs != {"wb_dat_o", "wb_ack_o", "wbc_ufm_irq"}:
    raise SystemExit("unexpected SC64 EFB wrapper interface")
ports = re.findall(r"\.(\w+)\(([^()]*)\)", instance[1])
params = re.findall(r"defparam EFBInst_0\.(\w+)\s*=\s*([^;]+);", source)
if len({name for name, _ in ports}) != len(ports) or not params:
    raise SystemExit("invalid EFB declaration inputs")
lines = ["/* Interface only; no behavioral implementation or bitstream qualification. */",
         "(* blackbox *) module EFB(" + ", ".join(name for name, _ in ports) + ");"]
for name, value in params:
    lines.append(f"    parameter {name} = {value.strip()};")
for name, signal in ports:
    root = signal.split("[")[0].strip()
    direction = "output" if not root or root in outputs else "input"
    lines.append(f"    {direction} {name};")
lines.append("endmodule")
Path(sys.argv[2]).write_text("\n".join(lines) + "\n")
