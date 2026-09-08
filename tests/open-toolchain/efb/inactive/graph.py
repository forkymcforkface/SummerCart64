"""Inventory direct upstream EFB routing edges from the pinned 7000 database."""
import json
import sys
sys.path.insert(0, '/usr/local/lib/trellis')
import pytrellis

pytrellis.load_database('/src/prjtrellis/database')
graph = pytrellis.Chip('LCMXO2-7000HC').get_routing_graph(False, False)
bel = next(b for t in graph.tiles.values() for b in t.bels.values() if graph.to_str(b.type) == 'EFB')
rows = {}
for pin, (wire, direction) in bel.pins.items():
    if direction != pytrellis.PortDirection.PORT_IN:
        continue
    arcs = []
    for upstream in graph.tiles[wire.loc].wires[wire.id].uphill:
        arc = graph.tiles[upstream.loc].arcs[upstream.id]
        source = arc.source
        arcs.append(dict(source=f'R{source.loc.y}C{source.loc.x}_{graph.to_str(source.id)}', configurable=arc.configurable))
    rows[graph.to_str(pin)] = arcs
for name in ('I2C1SCLI', 'I2C1SDAI', 'SPISCKI', 'SPIMISOI', 'SPIMOSII', 'UFMSN'):
    assert len(rows[name]) == 1 and not rows[name][0]['configurable']
    assert 'JPADDI' in rows[name][0]['source']
assert 'JPADDI' not in str(rows['I2C2SCLI']) + str(rows['I2C2SDAI'])
print(json.dumps(rows, indent=2))
