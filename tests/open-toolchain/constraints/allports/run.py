"""Exercise actual patched nextpnr LPF parsing and preserve the full SC64 LPF."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--nextpnr", required=True)
    ap.add_argument("--sc64", type=Path, required=True)
    ap.add_argument("--database", type=Path, default=Path("/src/prjtrellis/database"))
    args = ap.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent

    def run(name, command, expect=True, error=None):
        with (out / (name + ".log")).open("w") as log:
            proc = subprocess.run(
                command, stdout=log, stderr=subprocess.STDOUT, timeout=120
            )
        text = (out / (name + ".log")).read_text()
        if (proc.returncode == 0) != expect or (error and error not in text):
            raise RuntimeError(f"{name}: unexpected exit {proc.returncode}; see log")

    run(
        "synthesis",
        [
            "yosys",
            "-Q",
            "-T",
            "-p",
            f"read_verilog {here}/fixture.v; synth_lattice -family xo2 -top allports -json {out}/input.json",
        ],
    )
    base = [
        args.nextpnr,
        "--device",
        "LCMXO2-7000HC-6TG144C",
        "--json",
        str(out / "input.json"),
        "--lpf-allow-unconstrained",
        "--no-pack",
        "--no-place",
        "--no-route",
    ]

    def case(name, lpf, expect=True, error=None):
        path = out / (name + ".lpf")
        path.write_text(lpf)
        run(
            name,
            base + ["--lpf", str(path), "--write", str(out / (name + ".json"))],
            expect,
            error,
        )
        if expect:
            return json.loads((out / (name + ".json")).read_text())["modules"]["top"][
                "cells"
            ]

    positive = {
        "ordered": (
            'IOBUF ALLPORTS IO_TYPE=LVCMOS33 PULLMODE=DOWN;\nIOBUF PORT "a" PULLMODE=UP;\nIOBUF PORT "v[1]" PULLMODE=NONE;\nIOBUF PORT "b" DRIVE=8 SLEWRATE=FAST;\n',
            {"a": "UP", "v[1]": "NONE", "b": "DOWN", "d": "DOWN", "v[0]": "DOWN"},
        ),
        "allports_last": (
            'IOBUF PORT "a" PULLMODE=UP;\nIOBUF ALLPORTS IO_TYPE=LVCMOS33 PULLMODE=NONE;\n',
            {p: "NONE" for p in ("a", "b", "d", "v[0]", "v[1]")},
        ),
        "singleton": (
            'IOBUF ALLPORTS IO_TYPE=LVCMOS33 PULLMODE=NONE;\nIOBUF PORT "a[0]" PULLMODE="UP";\n',
            {"a": "UP", "b": "NONE", "d": "NONE", "v[0]": "NONE", "v[1]": "NONE"},
        ),
    }
    for name, (lpf, pulls) in positive.items():
        cells = case(name, lpf)
        for port, pull in pulls.items():
            attrs = cells[port]["attributes"]
            if attrs.get("IO_TYPE") != "LVCMOS33" or attrs.get("PULLMODE") != pull:
                raise RuntimeError(
                    "ordered port attributes differ: " + name + "/" + port
                )
        for name_, cell in cells.items():
            if not cell["type"].startswith("$nextpnr_") and any(
                k in cell["attributes"] for k in ("IO_TYPE", "PULLMODE")
            ):
                raise RuntimeError("ALLPORTS contaminated internal cell: " + name_)
        if name == "ordered" and any(
            cells["b"]["attributes"].get(k) != v
            for k, v in [("DRIVE", "8"), ("SLEWRATE", "FAST")]
        ):
            raise RuntimeError("per-port electrical attributes were lost")
    negative = [
        ("no_attrs", "IOBUF ALLPORTS;", "expected IOBUF"),
        ("no_port_attrs", 'IOBUF PORT "a";', "expected IOBUF attributes"),
        ("empty_value", "IOBUF ALLPORTS IO_TYPE=;", "expected IOBUF <attr>"),
        ("empty_key", "IOBUF ALLPORTS =LVCMOS33;", "expected IOBUF <attr>"),
        ("extra_equal", "IOBUF ALLPORTS IO_TYPE==LVCMOS33;", "expected IOBUF <attr>"),
        ("unknown", "IOBUF ALLPORTS SURPRISE=ON;", "unsupported IOBUF attribute"),
        ("ignored_key", "IOBUF ALLPORTS BANK_VCC=3.3;", "unsupported IOBUF attribute"),
        (
            "unknown_on_missing",
            'IOBUF PORT "absent" SURPRISE=ON;',
            "unsupported IOBUF attribute",
        ),
        ("bad_type", "IOBUF ALLPORTS IO_TYPE=BOGUS;", "unsupported IOBUF IO_TYPE"),
        ("bad_pull", "IOBUF ALLPORTS PULLMODE=FLOAT;", "unsupported IOBUF PULLMODE"),
        ("bad_drive", 'IOBUF PORT "b" DRIVE=999;', "unsupported IOBUF DRIVE"),
        ("empty_name", 'IOBUF PORT "" IO_TYPE=LVCMOS33;', "empty IOBUF PORT"),
        ("no_semicolon", "IOBUF ALLPORTS IO_TYPE=LVCMOS33", "unexpected end of LPF"),
    ]
    for name, lpf, error in negative:
        case(name, lpf, False, error)
    original = args.sc64.resolve() / "fw/project/lcmxo2/sc64.lpf"
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    run(
        "original-full-lpf",
        base + ["--lpf", str(original)],
        False,
        "unexpected SYSCONFIG key 'SDM_PORT'",
    )
    if hashlib.sha256(original.read_bytes()).hexdigest() != original_hash:
        raise RuntimeError("original LPF changed")
    pins = out / "pins.lpf"
    pins.write_text(
        positive["ordered"][0]
        + "\n".join(
            f'LOCATE COMP "{port}" SITE "{site}";'
            for port, site in (("a", 1), ("b", 2), ("v[0]", 3), ("v[1]", 10), ("d", 11))
        )
    )
    run(
        "route",
        [
            args.nextpnr,
            "--device",
            "LCMXO2-7000HC-6TG144C",
            "--json",
            str(out / "input.json"),
            "--lpf",
            str(pins),
            "--textcfg",
            str(out / "pins.config"),
        ],
    )
    run(
        "pack",
        [
            "ecppack",
            "--input",
            str(out / "pins.config"),
            "--bit",
            str(out / "diagnostic.bit"),
        ],
    )
    run(
        "unpack",
        ["ecpunpack", str(out / "diagnostic.bit"), str(out / "unpacked.config")],
    )

    def config_enums(path):
        result = {}
        tile = None
        for line in path.read_text().splitlines():
            if line.startswith(".tile "):
                tile = line[6:]
            elif line.startswith("enum: "):
                _, key, value = line.split()
                result[tile, key] = value
        return result

    requested = config_enums(out / "pins.config")
    decoded = config_enums(out / "unpacked.config")
    aliases = []
    database_hashes = {}
    for (tile, key), value in requested.items():
        if not key.startswith("PIO"):
            continue
        observed = decoded.get((tile, key))
        if observed == value:
            continue
        db = args.database / "MachXO2/tiledata" / tile.split(":")[1] / "bits.db"
        database_hashes[str(db)] = hashlib.sha256(db.read_bytes()).hexdigest()
        choices = {}
        current = None
        for line in db.read_text().splitlines():
            if line.startswith(".config_enum "):
                current = line.split()[1]
            elif not line or line.startswith("."):
                current = None
            elif current == key:
                parts = line.split()
                choices[parts[0]] = set(parts[1:])
        if (
            value not in choices
            or observed not in choices
            or choices[value] != choices[observed]
        ):
            raise RuntimeError(
                f"electrical configuration changed: {tile} {key}: {value} -> {observed}"
            )
        aliases.append(
            {"tile": tile, "attribute": key, "requested": value, "decoded": observed}
        )
    result = {
        "electrical_pack_unpack": True,
        "database_aliases": aliases,
        "database_hashes": database_hashes,
        "positive_cases": len(positive),
        "negative_cases": len(negative),
        "original_lpf_sha256": original_hash,
        "original_lpf_next_error": "SYSCONFIG SDM_PORT",
        "full_lpf_qualified": False,
        "hardware_qualified": False,
    }
    (out / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
