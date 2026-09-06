"""Prove write addresses equal paired read addresses whenever a write is enabled."""

import copy
import json
import subprocess
from pathlib import Path


def prove_addresses(design, module, names, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    source = design["modules"][module]["cells"]
    drivers = {
        b: (n, c)
        for n, c in source.items()
        for p, v in c["connections"].items()
        if c["port_directions"][p] == "output"
        for b in v
        if isinstance(b, int)
    }
    cells = {}
    leaves = set()
    visited = set()

    def visit(b):
        if not isinstance(b, int) or b in visited:
            return
        visited.add(b)
        pair = drivers.get(b)
        if pair is None or pair[1]["type"] not in (
            "$mux",
            "$pmux",
            "$and",
            "$or",
            "$not",
            "$logic_not",
            "$logic_and",
            "$logic_or",
            "$eq",
            "$ne",
            "$reduce_or",
            "$reduce_and",
            "$reduce_bool",
        ):
            leaves.add(b)
            return
        n, c = pair
        cells[n] = copy.deepcopy(c)
        for p, v in c["connections"].items():
            if c["port_directions"][p] == "input":
                for x in v:
                    visit(x)

    nextbit = (
        max(
            b
            for c in source.values()
            for v in c["connections"].values()
            for b in v
            if isinstance(b, int)
        )
        + 1
    )
    flags = []
    for n in names:
        c = source[n]
        q = c["connections"]
        p = c["parameters"]
        a = int(p["ABITS"], 2)
        w = int(p["WIDTH"], 2)
        for port in range(2):
            ra = q["RD_ADDR"][port * a : (port + 1) * a]
            wa = q["WR_ADDR"][port * a : (port + 1) * a]
            en = q["WR_EN"][port * w : port * w + 1]
            for b in ra + wa + en:
                visit(b)
            eq, good = nextbit, nextbit + 1
            nextbit += 2
            cells[n + f"$address_equal{port}"] = {
                "type": "$eq",
                "parameters": {
                    "A_WIDTH": a,
                    "B_WIDTH": a,
                    "Y_WIDTH": 1,
                    "A_SIGNED": 0,
                    "B_SIGNED": 0,
                },
                "attributes": {},
                "port_directions": {"A": "input", "B": "input", "Y": "output"},
                "connections": {"A": ra, "B": wa, "Y": [eq]},
            }
            cells[n + f"$address_guard{port}"] = {
                "type": "$mux",
                "parameters": {"WIDTH": 1},
                "attributes": {},
                "port_directions": {
                    "A": "input",
                    "B": "input",
                    "S": "input",
                    "Y": "output",
                },
                "connections": {"A": ["1"], "B": [eq], "S": en, "Y": [good]},
            }
            flags.append(good)
    fixture = {
        "modules": {
            "addresses": {
                "attributes": {},
                "ports": {
                    "inputs": {"direction": "input", "bits": sorted(leaves)},
                    "valid": {"direction": "output", "bits": flags},
                },
                "cells": cells,
                "netnames": {},
            }
        }
    }
    path = out / "addresses.json"
    path.write_text(json.dumps(fixture))
    script = out / "addresses.ys"
    script.write_text(
        f"read_json {path}\nhierarchy -top addresses\nsat -enable_undef -set-def-inputs -prove valid {len(flags)}'b"
        + ("1" * len(flags))
        + " -verify\n"
    )
    with (out / "addresses.log").open("w") as log:
        subprocess.run(
            ["yosys", "-Q", "-T", "-s", str(script)],
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=120,
            check=True,
        )
    return len(flags)
