"""Read physical EBR fields and correlate a separately exported NCL artifact.

This diagnostic emits no configuration. Artifact association is supplied by
the caller; matching site/mode records do not prove NCD-to-BIT identity.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re


def ncl_sites(text):
    """Extract the narrow vendor EBR component form, rejecting ambiguity."""
    sites = {}
    for block in re.split(r"(?m)^   comp ", text)[1:]:
        if "cellmodel-name EBR;" not in block:
            continue
        location = re.findall(r"\bsite EBR_R(\d+)C(\d+);", block)
        mode = re.findall(r'program "MODE:(DP8KC|PDPW8KC|FIFO8KB) ', block)
        if len(location) != 1 or len(mode) != 1:
            raise ValueError("Ambiguous or unsupported EBR component")
        row, column = map(int, location[0])
        key = f"EBR_R{row}C{column + 1}:EBR1"
        if key in sites:
            raise ValueError("Duplicate physical EBR site")
        sites[key] = {
            "mode": mode[0],
            "site": f"EBR_R{row}C{column}",
            "wid": re.findall(r"\bWID=0b([01]+)", block),
            "rid": re.findall(r"\bRID=([^,\s]+)", block),
        }
    if not sites:
        raise ValueError("No recognized EBR components")
    return sites


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--bit", type=Path, required=True)
    parser.add_argument("--ncl", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import pytrellis

    model = ncl_sites(args.ncl.read_text())
    database_file = args.database / "MachXO2/tiledata/EBR1/bits.db"
    database_text = database_file.read_text()
    match = re.search(r"\.config_enum EBR.MODE NONE\n(.*?)\n\n",
                      database_text, re.S)
    if not match:
        raise ValueError("Missing mode database")
    patterns = {}
    for line in match[1].splitlines():
        parts = line.split()
        patterns[parts[0]] = parts[1:]
    pytrellis.load_database(str(args.database))
    chip = pytrellis.Bitstream.read_bit(str(args.bit)).deserialise_chip()
    results = {}
    for name, tile in chip.tiles.items():
        if tile.info.type != "EBR1":
            continue
        value = sum(int(tile.cram.bit(1, 32 + bit)) << bit for bit in range(5))
        entry = {"field": value, "ncl": model.get(name)}
        if name in model:
            unmet = []
            for token in patterns[model[name]["mode"]]:
                bit = re.fullmatch(r"(!?)F(\d+)B(\d+)", token)
                if not bit:
                    raise ValueError(f"Unsupported mode token {token}")
                invert, frame, offset = bit.groups()
                if bool(tile.cram.bit(int(frame), int(offset))) == bool(invert):
                    unmet.append(token)
            entry["unmet_mode_tokens"] = unmet
        results[name] = entry
    if model.keys() - results.keys():
        raise ValueError("NCL sites are absent from decoded device")
    output = {
        "device": chip.info.name,
        "inputs": {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in (args.bit, args.ncl, database_file)},
        "ncl_components": len(model),
        "sites": results,
    }
    args.output.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
