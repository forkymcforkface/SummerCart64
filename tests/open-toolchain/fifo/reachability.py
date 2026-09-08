"""nextpnr post-place diagnostic: every physical FIFO flag must have an outgoing edge."""
import json

rows = []
for bel in ctx.getBels():
    if ctx.getBelType(bel) != 'DP8KC':
        continue
    flags = {}
    for pin in ('AE', 'AF', 'EF', 'FF'):
        wire = ctx.getBelPinWire(bel, pin)
        flags[pin] = {'wire': wire, 'downhill_pips': len(list(ctx.getPipsDownhill(wire)))}
    rows.append({'bel': bel, 'flags': flags})
print('FIFO_FLAG_REACHABILITY=' + json.dumps(rows))
