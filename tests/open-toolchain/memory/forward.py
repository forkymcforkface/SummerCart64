"""Experimental old-data collision forwarding for selected Yosys dual-port RAMs."""

import argparse
import json
from address_proof import prove_addresses
from pathlib import Path


def transform(design, module, names, proof_directory):
    prove_addresses(design, module, names, proof_directory)

    def require(condition):
        if not condition:
            raise ValueError("unsupported RAM shape; refusing forwarding transform")

    m = design["modules"][module]
    cells = m["cells"]
    nextbit = (
        max(
            b
            for c in cells.values()
            for v in c["connections"].values()
            for b in v
            if isinstance(b, int)
        )
        + 1
    )

    def bits(n=1):
        nonlocal nextbit
        out = list(range(nextbit, nextbit + n))
        nextbit += n
        return out

    for name in names:
        c = cells[name]
        p = c["parameters"]
        q = c["connections"]

        def number(k):
            return int(p[k], 2)

        require(c["type"] == "$mem_v2")
        require(number("RD_PORTS") == number("WR_PORTS") == 2)
        require(number("RD_CLK_ENABLE") == number("WR_CLK_ENABLE") == 3)
        require(number("RD_CLK_POLARITY") == number("WR_CLK_POLARITY") == 3)
        require(number("RD_TRANSPARENCY_MASK") == number("RD_COLLISION_X_MASK") == 0)
        require(number("WR_PRIORITY_MASK") == 4)
        require(number("RD_WIDE_CONTINUATION") == number("WR_WIDE_CONTINUATION") == 0)
        require(number("OFFSET") == 0 and number("SIZE") == 2 ** number("ABITS"))
        require(q["RD_CLK"] == q["WR_CLK"] == [q["RD_CLK"][0]] * 2)
        require(q["RD_ARST"] == q["RD_SRST"] == ["0", "0"])
        for key in ("RD_INIT_VALUE", "RD_ARST_VALUE", "RD_SRST_VALUE"):
            require(set(p[key]) == {"x"})
        w, a = number("WIDTH"), number("ABITS")
        wa, wb = q["WR_EN"][0:1], q["WR_EN"][w : w + 1]
        require(q["WR_EN"] == wa * w + wb * w)
        aa, ab = q["RD_ADDR"][:a], q["RD_ADDR"][a:]
        en = list(q["RD_EN"])
        oldout = list(q["RD_DATA"])

        def cell(suffix, typ, inputs, width=1, output=None):
            out = bits(width) if output is None else output
            params = (
                {"WIDTH": width}
                if typ in ("$dff",)
                else {
                    "A_SIGNED": 0,
                    "B_SIGNED": 0,
                    "A_WIDTH": len(inputs["A"]),
                    "B_WIDTH": len(inputs["B"]),
                    "Y_WIDTH": width,
                }
            )
            if typ == "$mux":
                params = {"WIDTH": width}
            if typ == "$dff":
                params = {"WIDTH": width, "CLK_POLARITY": 1}
            port = "Q" if typ == "$dff" else "Y"
            cells[name + "$repair$" + suffix] = {
                "hide_name": 1,
                "type": typ,
                "parameters": params,
                "attributes": {},
                "port_directions": {k: "input" for k in inputs} | {port: "output"},
                "connections": inputs | {port: out},
            }
            return out

        same = cell("same", "$eq", {"A": aa, "B": ab})
        bcollision = cell("bwrite_same", "$and", {"A": same, "B": wb})
        effective_a = cell(
            "effective_a", "$mux", {"A": wa, "B": ["0"], "S": bcollision}
        )
        acollision = cell("awrite_same", "$and", {"A": same, "B": effective_a})
        q["WR_EN"] = effective_a * w + wb * w
        q["WR_ADDR"] = aa + ab
        read_a = cell("read_a", "$mux", {"A": ["1"], "B": ["0"], "S": bcollision})
        read_b = cell("read_b", "$mux", {"A": ["1"], "B": ["0"], "S": acollision})
        q["RD_EN"] = read_a + read_b
        raw = bits(2 * w)
        q["RD_DATA"] = raw
        p["WR_PRIORITY_MASK"] = "0000"
        p["RD_COLLISION_X_MASK"] = "0110"
        for i, collision in enumerate((bcollision, acollision)):
            delayed = cell(
                "select" + str(i), "$dff", {"D": collision, "CLK": q["RD_CLK"][:1]}
            )
            repaired = cell(
                "data" + str(i),
                "$mux",
                {
                    "A": raw[i * w : (i + 1) * w],
                    "B": raw[(1 - i) * w : (2 - i) * w],
                    "S": delayed,
                },
                w,
            )
            active = cell(
                "enable" + str(i), "$dff", {"D": en[i : i + 1], "CLK": q["RD_CLK"][:1]}
            )
            held = cell(
                "hold" + str(i),
                "$dff",
                {"D": oldout[i * w : (i + 1) * w], "CLK": q["RD_CLK"][:1]},
                w,
            )
            cell(
                "output" + str(i),
                "$mux",
                {"A": held, "B": repaired, "S": active},
                w,
                oldout[i * w : (i + 1) * w],
            )
    return design


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("module")
    ap.add_argument("memories", nargs="+")
    args = ap.parse_args()
    data = json.loads(args.input.read_text())
    args.output.write_text(
        json.dumps(
            transform(
                data,
                args.module,
                args.memories,
                args.output.parent / (args.output.stem + "-addresses"),
            )
        )
    )
