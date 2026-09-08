"""Prepare a routing-only EFB netlist by excluding dedicated-path simulation ties.

No physical tie value is synthesized by this operation. Package-pin electrical
behavior and EFB configuration remain unqualified; nextpnr's EFB bitstream
barrier must remain enabled. Fabric inputs and Wishbone/UFM state are preserved.
"""
import argparse
import copy
import json
from pathlib import Path

PAD_ZERO = ('I2C1SCLI', 'I2C1SDAI', 'SPISCKI', 'SPIMISOI', 'SPIMOSII')
PLL_ZERO = tuple(f'PLL{pll}DATI{bit}' for pll in range(2) for bit in range(8)) + ('PLL0ACKI', 'PLL1ACKI')
REMOVE = dict.fromkeys(PAD_ZERO + PLL_ZERO, '0') | {'UFMSN': '1'}


def prepare(source):
    data = copy.deepcopy(source)
    removed = []
    for module in data['modules'].values():
        cells = module.get('cells', {})
        drivers = {}
        for cell in cells.values():
            for port, direction in cell.get('port_directions', {}).items():
                if direction == 'output':
                    for bit in cell['connections'].get(port, []):
                        drivers.setdefault(bit, []).append((cell['type'], port))
        constants = {'0': '0', '1': '1'}
        for bit, owners in drivers.items():
            if owners == [('VLO', 'Z')]:
                constants[bit] = '0'
            elif owners == [('VHI', 'Z')]:
                constants[bit] = '1'
        for cell in cells.values():
            if cell['type'] == 'EHXPLLJ' and cell.get('parameters', {}).get('PLL_USE_WB') != 'DISABLED':
                raise ValueError('PLL Wishbone interface must be explicitly disabled')
        for name, cell in cells.items():
            if cell['type'] != 'EFB':
                continue
            params = cell.get('parameters', {})
            if params.get('DEV_DENSITY') != '7000L' or params.get('EFB_UFM') != 'ENABLED':
                raise ValueError('requires exact SC64 density and enabled UFM')
            for peripheral in ('EFB_I2C1', 'EFB_I2C2', 'EFB_SPI', 'EFB_TC'):
                if params.get(peripheral) != 'DISABLED':
                    raise ValueError(peripheral + ' must be explicitly disabled')
            for port, direction in cell['port_directions'].items():
                if direction == 'output' and not (port.startswith('WBDATO') or port in ('WBACKO', 'WBCUFMIRQ')):
                    if cell['connections'].get(port):
                        raise ValueError('unexpected connected peripheral output ' + port)
            for port, value in REMOVE.items():
                bits = cell['connections'].get(port, [])
                if len(bits) != 1 or constants.get(bits[0]) != value:
                    raise ValueError('requires exact simulation tie ' + port + '=' + value)
            for port, value in REMOVE.items():
                del cell['connections'][port]
                del cell['port_directions'][port]
                removed.append(dict(cell=name, port=port, value=value))
            cell.setdefault('attributes', {})['SC64_EFB_DEDICATED_TIES_DIAGNOSTIC'] = '1'
    if not removed:
        raise ValueError('no exact SC64 EFB instance found')
    return data, removed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--diagnostic', action='store_true', required=True)
    args = parser.parse_args()
    result, removed = prepare(json.loads(args.input.read_text()))
    with args.output.open('x') as output:
        json.dump(result, output)
    print(json.dumps(dict(removed=removed, count=len(removed), qualified=False)))
