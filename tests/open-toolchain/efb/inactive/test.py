"""Check the exact inactive-tie boundary against an existing SC64 Yosys netlist."""
import copy
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
from prepare import prepare, REMOVE

original = json.loads(Path(sys.argv[1]).read_text())
snapshot = copy.deepcopy(original)
result, ledger = prepare(original)
assert original == snapshot
assert len(ledger) == 24
for module_name, module in original['modules'].items():
    for name, cell in module.get('cells', {}).items():
        out = result['modules'][module_name]['cells'][name]
        if cell['type'] != 'EFB':
            assert cell == out
            continue
        restored = copy.deepcopy(out)
        restored['attributes'].pop('SC64_EFB_DEDICATED_TIES_DIAGNOSTIC')
        for port in REMOVE:
            restored['connections'][port] = cell['connections'][port]
            restored['port_directions'][port] = cell['port_directions'][port]
        assert restored == cell

def efb(data):
    return next(c for m in data['modules'].values() for c in m.get('cells', {}).values() if c['type'] == 'EFB')

cases = []
for parameter in ('EFB_I2C1', 'EFB_I2C2', 'EFB_SPI', 'EFB_TC'):
    data = copy.deepcopy(original)
    efb(data)['parameters'][parameter] = 'ENABLED'
    cases.append(data)
for port in REMOVE:
    data = copy.deepcopy(original)
    efb(data)['connections'][port] = [987654321]
    cases.append(data)
for port in ('UFMSN', 'I2C1SCLI'):
    data = copy.deepcopy(original)
    efb(data)['connections'][port] = ['0' if REMOVE[port] == '1' else '1']
    cases.append(data)
data = copy.deepcopy(original)
efb(data)['connections']['I2C1IRQO'] = [987654321]
cases.append(data)
data = copy.deepcopy(original)
pll = next(c for m in data['modules'].values() for c in m.get('cells', {}).values() if c['type'] == 'EHXPLLJ')
pll['parameters']['PLL_USE_WB'] = 'ENABLED'
cases.append(data)
for data in cases:
    before = copy.deepcopy(data)
    try:
        prepare(data)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid input accepted')
    assert data == before
print(f'PASS exact 24 dedicated ties; all other cells, parameters, and connections preserved; {len(cases)} rejected mutations')
