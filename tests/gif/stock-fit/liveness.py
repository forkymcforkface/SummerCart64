"""Check structural data paths in the synthesis skeleton, not SPI behavior.

Clock/reset edges are excluded from graph reachability. Deliberate start and
status disconnections must fail the same gate. This is not temporal proof.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def check(top):
    nets=top['netnames']
    required=['gif_engine.decoder.busy','gif_status','mcu_top_inst.gif_status']
    if any(n not in nets for n in required):
        raise ValueError('missing data path node: status boundary')
    busy=nets[required[0]]['bits']
    if (len(busy)!=1 or not isinstance(busy[0],int)
            or nets['gif_status']['bits'][10]!=busy[0]
            or nets['mcu_top_inst.gif_status']['bits'][10]!=busy[0]):
        raise ValueError('missing data path: dedicated decoder busy status wire')
    graph = defaultdict(set)
    for cell in top['cells'].values():
        connections = cell['connections']
        inputs = [b for p, bs in connections.items()
            if cell['port_directions'][p] == 'input'
            and p.upper() not in {'CLK','C','CLOCK','ARST','SRST','RESET','RST'}
            for b in bs if isinstance(b,int)]
        outputs = [b for p, bs in connections.items()
            if cell['port_directions'][p] == 'output' for b in bs if isinstance(b,int)]
        for b in inputs:
            graph[b].update(outputs)
    def bits(name):
        if name not in top['netnames']:
            raise ValueError('missing data path node: '+name)
        return set(b for b in top['netnames'][name]['bits'] if isinstance(b,int))
    def reaches(source, target):
        seen = bits(source)
        todo = list(seen)
        while todo:
            for bit in graph[todo.pop()] - seen:
                seen.add(bit)
                todo.append(bit)
        if not bits(target) or not seen.intersection(bits(target)):
            raise ValueError(f'missing data path {source} -> {target}')
    for source,target in [('mcu_mosi','gif_control'),
        ('gif_control','gif_engine.decoder.start'),
        ('gif_engine.decoder.busy','mcu_top_inst.gif_status'),
        ('gif_engine.decoder.busy','gif_status'),('gif_engine.decoder.busy','mcu_miso'),
        ('gif_control','gif_engine.output_bus.request')]:
        reaches(source,target)
    if top['netnames']['gif_engine.decoder.start']['bits'] == ['0']:
        raise ValueError('disconnected decoder start')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('netlist',type=Path)
    a=p.parse_args()
    top=json.loads(a.netlist.read_text())['modules']['top']
    check(top)
    print(json.dumps({'structural_paths':'PASS',
        'functional_spi_api_test':False,'physical_qualification':False}))


if __name__=='__main__':
    main()
