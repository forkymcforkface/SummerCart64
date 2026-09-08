"""Inspect installed Diamond data without exporting its database contents.

This is a bounded schema probe, not a timing importer. Named SPD records are
accepted only when local length/count sentinels agree. The four integer slots
remain unnamed; an SDF envelope match does not establish their physical roles.
"""

import argparse
import collections
import hashlib
import json
import pathlib
import re
import struct
import zlib

SPD_HASHES = {
    "xo2c1200": "008635b8d16a16cc269076617fee6d413014c17765816c06a3dbbf57637b4c47",
    "xo2c7000": "af2d8aa9a00f86171c134b496ad3e6bc44bc256acdbd7b3099de10392ae399c1",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def tld_probe(data):
    if data[:10] != b" _$COMP\0\x32\0":
        raise ValueError("unrecognized TLD wrapper")
    offset = 10
    chunks = []
    decoded = bytearray()
    while offset < len(data):
        if offset + 4 > len(data):
            raise ValueError("truncated chunk length")
        size = struct.unpack_from(">I", data, offset)[0]
        offset += 4
        if not size or offset + size > len(data):
            raise ValueError("invalid chunk size")
        stream = zlib.decompressobj()
        block = stream.decompress(data[offset:offset + size], 8193)
        if not stream.eof or stream.unused_data or len(block) > 8192:
            raise ValueError("invalid compressed chunk")
        decoded.extend(block)
        chunks.append([size, len(block)])
        offset += size
    if not chunks or not decoded:
        raise ValueError("empty TLD payload")
    strings = re.findall(rb"[ -~]{5,}", decoded)
    return {"sha256": digest(data), "chunks": chunks,
            "decoded_bytes": len(decoded), "decoded_sha256": digest(decoded),
            "assembly_names": sum(s.endswith(b"_ASS") for s in strings),
            "strings": len(strings)}


def spd_records(data, device):
    if device not in SPD_HASHES or digest(data) != SPD_HASHES[device]:
        raise ValueError("SPD schema is qualified only for the two pinned files")
    sections = list(re.finditer(rb"Final 34[.]4[^\n]*\n" +
                               device.encode() + rb"\n", data))
    if len(sections) != 8:
        raise ValueError("unrecognized SPD section inventory")
    records = []
    labels = []
    for index, section in enumerate(sections):
        label = section.group().split(b"\0")[-1].split(b"\n")[0].decode()
        labels.append(label)
        end = sections[index + 1].start() if index + 1 < len(sections) else len(data)
        for match in re.finditer(rb"[A-Z][A-Z0-9_]*_(?:DEL|SET|HLD|MPW)\0", data[section.end():end]):
            pos = section.end() + match.start()
            name = match.group()[:-1]
            if pos < 19 or data[pos - 19] != 4:
                continue
            if struct.unpack_from(">H", data, pos - 2)[0] != len(name):
                continue
            condition_pos = pos + len(name) + 1
            size = struct.unpack_from(">H", data, condition_pos)[0]
            condition_pos += 2
            condition = data[condition_pos:condition_pos + size]
            if data[condition_pos + size:condition_pos + size + 2] != b"\0\xff":
                continue
            if any(c < 32 or c > 126 for c in condition):
                continue
            records.append({"grade": label, "name": name.decode(),
                            "condition": condition.decode(),
                            "slots": list(struct.unpack_from(">4i", data, pos - 18))})
    if labels != ["M", "L", "6", "5", "4", "3", "2", "1"]:
        raise ValueError("unexpected SPD grades")
    if len(records) != 31112:
        raise ValueError("record inventory changed")
    return labels, records


def hard_inventory(records):
    groups = {"FIFO8KB": [], "IDDR_ODDR": [], "EFB_condition": [], "EFB_WB_UFM_names": []}
    for row in records:
        if row["grade"] != "6":
            continue
        for group in ("FIFO8KB", "IDDR_ODDR"):
            if group in row["condition"]:
                groups[group].append(row)
        if "EFB:::" in row["condition"]:
            groups["EFB_condition"].append(row)
        if row["name"].startswith(("WB", "WCLK", "UFM")):
            groups["EFB_WB_UFM_names"].append(row)
    return {group: {"records": len(rows), "names": dict(sorted(collections.Counter(
        row["name"] for row in rows).items()))} for group, rows in groups.items()}


def selected(records, name, grade="6"):
    rows = [r for r in records if r["grade"] == grade and r["name"] == name
            and "CLKMUX:CLK:::CLK=#SIG" in r["condition"]
            and (name in ("REG_DEL", "CE_SET", "CE_HLD") or "REGMODE:FF" in r["condition"])]
    values = sorted(set(tuple(r["slots"]) for r in rows))
    if len(values) != 1:
        raise ValueError("ambiguous selected record: " + name)
    return list(values[0])


def oracle_cell(oracle):
    """Select the one known SDF cell; this is not a general SDF importer."""
    if re.findall(r'\(TIMESCALE\s+([^)]*)\)', oracle) != ['1ps'] or \
            re.findall(r'\(DESIGN\s+"([^"]*)"\)', oracle) != ['control_soc_demo']:
        raise ValueError("wrong oracle identity or timescale")
    marker = '(CELLTYPE "adc_wb_inst_adc_inst_SSD_ADC_SLICE_0")'
    if oracle.count(marker) != 1:
        raise ValueError("oracle cell missing or ambiguous")
    marker_pos = oracle.index(marker)
    start = oracle.rfind('(CELL', 0, marker_pos)
    if start < 0 or oracle[start:marker_pos].strip() != '(CELL':
        raise ValueError("oracle cell wrapper missing")
    depth = 0
    quoted = escaped = False
    for pos in range(start, len(oracle)):
        char = oracle[pos]
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                cell = oracle[start:pos + 1]
                instances = re.findall(r'\(INSTANCE\s+([^)]*)\)', cell)
                if instances != [r'adc_wb_inst\/adc_inst\/SSD_ADC\/SLICE_0']:
                    raise ValueError("wrong oracle cell instance")
                return cell
    raise ValueError("truncated oracle cell")


def minimum_oracle_check(oracle):
    cell = oracle_cell(oracle)
    if "(IOPATH CLK Q0 (133:143:154)" not in cell:
        raise ValueError("minimum oracle clock-to-Q missing in selected cell")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=pathlib.Path)
    parser.add_argument("--oracle", required=True, type=pathlib.Path)
    parser.add_argument("--minimum-oracle", required=True, type=pathlib.Path)
    args = parser.parse_args()
    result = {"status": "schema probe only; not a timing qualification", "devices": {}}
    for device in ("xo2c1200", "xo2c7000"):
        spd = (args.data / (device + ".spd")).read_bytes()
        grades, records = spd_records(spd, device)
        result["devices"][device] = {
            "spd_sha256": digest(spd), "spd_bytes": len(spd), "grades": grades,
            "recognized_records": len(records),
            "hard_block_inventory": hard_inventory(records),
            "grade6_ff": {name: selected(records, name)
                          for name in ("REG_DEL", "M_SET", "M_HLD", "CE_SET", "CE_HLD")},
            "tld": tld_probe((args.data / (device + ".tld")).read_bytes())}
    oracle = args.oracle.read_text()
    expected = {"REG_DEL": (320, 343, 367), "M_SET": (202, 230, 258),
                "M_HLD": (-118, -106, -94), "CE_SET": (176, 196, 217),
                "CE_HLD": (-76, -68, -61)}
    checks = {}
    first_cell = oracle_cell(oracle)
    if not re.search(r'IOPATH CLK Q0 \(320:343:367\)', first_cell):
        raise ValueError("clock-to-Q oracle missing")
    for pin, setup, hold in (("M0", "202:230:258", "-118:-106:-94"),
                             ("CE", "176:196:217", "-76:-68:-61")):
        if "(SETUPHOLD " + pin + " (posedge CLK) (" + setup + ")(" + hold + "))" not in first_cell:
            raise ValueError("setup/hold oracle missing")
    for name, triple in expected.items():
        values = result["devices"]["xo2c1200"]["grade6_ff"][name]
        envelope = (min(values), int((min(values) + max(values)) / 2), max(values))
        literal = "(" + ":".join(str(v) for v in triple) + ")"
        if envelope != triple or literal not in first_cell:
            raise ValueError("oracle mismatch: " + name)
        checks[name] = {"envelope_ps": envelope, "oracle_literal_present": True}
    result["oracle_checks"] = checks
    result["oracle_sha256"] = digest(args.oracle.read_bytes())
    minimum = args.minimum_oracle.read_text()
    minimum_oracle_check(minimum)
    _, rows = spd_records((args.data / "xo2c1200.spd").read_bytes(), "xo2c1200")
    raw = selected(rows, "REG_DEL", "M")
    if (min(raw), max(raw)) == (133, 154):
        raise ValueError("minimum mismatch counterexample disappeared")
    result["minimum_counterexample"] = {
        "M_REG_DEL_slots": raw, "oracle_ps": [133, 143, 154],
        "direct_envelope_matches": False,
        "status": "additional vendor transformation or selection unresolved",
        "oracle_sha256": digest(args.minimum_oracle.read_bytes())}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()


