"""Correct FIFO output direction in the pinned MachXO2 routing database/fuzzer."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
pending = {}
for tile in ('EBR0', 'EBR0_END'):
    path = root / 'database/MachXO2/tiledata' / tile / 'bits.db'
    text = path.read_text()
    for flag, route in (('AE', 'E1_JQ4'), ('AF', 'E1_JF4'), ('EF', 'E1_JQ3'), ('FF', 'E1_JF3')):
        old = f'.fixed_conn J{flag}_EBR {route}'
        new = f'.fixed_conn {route} J{flag}_EBR'
        if new in text:
            continue
        if text.count(old) != 1:
            raise SystemExit(f'{path}: expected flag connection missing')
        text = text.replace(old, new)
    pending[path] = text
path = root / 'fuzzers/machxo2/040-ebr_routing/mk_nets.py'
text = path.read_text()
for flag in ('AE', 'AF', 'EF', 'FF'):
    old = f'J{flag}_EBR".format(tile[0], tile[1]), "sink"'
    new = old.replace('"sink"', '"driver"')
    if new not in text:
        if text.count(old) != 1:
            raise SystemExit(f'{path}: flag direction missing')
        text = text.replace(old, new)
pending[path] = text
for path, text in pending.items():
    path.write_text(text)
print('Corrected four FIFO flag outputs in both MachXO2 EBR tile types and the generating fuzzer')
