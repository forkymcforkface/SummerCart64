"""Report every installed example NCD without using folder names as part IDs.

Outputs belong in an explicitly supplied ignored directory. Vendor-generated
netlists/SDF stay there; this script does not compile or program a design.
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import pathlib
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diamond", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output must be new")
    args.output.mkdir(parents=True)
    foundry = args.diamond / "ispfpga"
    env = dict(os.environ, FOUNDRY=str(foundry),
               LD_LIBRARY_PATH=str(foundry / "bin/lin64"))
    sources = sorted((args.diamond / "examples").rglob("*.ncd"))

    def run(item):
        index, ncd = item
        output = args.output / str(index)
        output.mkdir()
        prf = ncd.with_suffix(".prf")
        if not prf.exists() and ncd.stem.endswith("_map"):
            prf = ncd.with_name(ncd.stem[:-4] + ".prf")
        if not prf.exists() and ncd.parent.name.endswith(".dir"):
            prf = ncd.parent.with_suffix(".prf")
        command = [str(foundry / "bin/lin64/ldbanno"), "-n", "verilog", "-neg",
                   "-o", str(output / "netlist.v"), "-d", str(output / "timing.sdf"), str(ncd)]
        if prf.exists():
            command.append(str(prf))
        with (output / "report.log").open("w") as log:
            try:
                status = subprocess.run(command, env=env, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=20).returncode
            except subprocess.TimeoutExpired:
                status = 124
        log = (output / "report.log").read_text(errors="replace")
        evidence = [line for line in log.splitlines()
                    if re.search(r"device|part|performance|speed", line, re.I)]
        text = ""
        for name in ("netlist.v", "timing.sdf"):
            path = output / name
            if path.exists():
                text += path.read_text(errors="replace")
        markers = {name: len(re.findall(pattern, text)) for name, pattern in {
            "efb_wishbone": r"\b(?:WBCLKI|WBCYCI|WBSTBI|WBACKO)\b",
            "fifo": r"\b(?:FIFO8KB|FIFO8KA)\b",
            "oddr": r"\b(?:ODDRXE|ODDRX2[A-Z]*|ODDRX1[A-Z]*)\b",
        }.items()}
        result = {"index": index, "ncd": str(ncd.relative_to(args.diamond)),
                  "ncd_sha256": hashlib.sha256(ncd.read_bytes()).hexdigest(),
                  "preference": str(prf) if prf.exists() else None,
                  "exit": status, "part_evidence": evidence, "text_markers": markers}
        print(json.dumps(result), flush=True)
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, enumerate(sources)))
    (args.output / "inventory.json").write_text(json.dumps(results, indent=2))
    print("COMPLETE: {} installed NCD files".format(len(results)), flush=True)


if __name__ == "__main__":
    main()
