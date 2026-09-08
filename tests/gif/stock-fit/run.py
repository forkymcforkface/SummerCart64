"""Run paired mapping and actual disconnected-RTL liveness negatives.

No placement or bitstream generation is permitted by this research runner.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest',type=Path)
    p.add_argument('decoder',type=Path)
    p.add_argument('mux',type=Path)
    p.add_argument('nextpnr',type=Path)
    p.add_argument('output',type=Path)
    a=p.parse_args()
    here=Path(__file__).resolve().parent
    out=a.output.resolve()
    if out.exists() or here.parents[1] in out.parents:
        p.error('fresh output outside tests required')
    out.mkdir(parents=True)
    tools=here.parents[1]/'open-toolchain'
    manifest=json.loads(a.manifest.read_text())
    if hashlib.sha256((a.manifest.parent/'converted.v').read_bytes()).hexdigest()!=manifest['converted_sha256']:
        raise ValueError('stock conversion hash mismatch')
    top=next(Path(x) for x in manifest['command'] if x.endswith('/rtl/top.sv'))
    project=top.parents[1]/'project/lcmxo2'
    def run(cmd,log,expected=0):
        with log.open('w') as f:
            code=subprocess.run(list(map(str,cmd)),cwd=project,stdout=f,
                stderr=subprocess.STDOUT,timeout=600).returncode
        if code!=expected:
            raise ValueError(f'exit {code}, expected {expected}: {log}')
    for kind in ['candidate','start','status']:
        command=['/usr/bin/python3',here/'generate.py',a.manifest,a.decoder,a.mux,out/kind]
        if kind!='candidate':command+=['--disconnect',kind]
        run(command,out/(kind+'-generate.log'))
    for kind,converted in [('stock',a.manifest.parent/'converted.v'),
                           ('candidate',out/'candidate/converted.v')]:
        run(['/usr/bin/python3',tools/'memory/full.py',converted,project,out/(kind+'-map')],out/(kind+'-map.log'))
    run(['/usr/bin/python3',here/'liveness.py',out/'candidate-map/original.json'],out/'liveness.log')
    tops=[json.loads((out/(k+'-map')/'original.json').read_text())['modules']['top']
          for k in ['stock','candidate']]
    ports=[{n:(p['direction'],len(p['bits'])) for n,p in t['ports'].items()} for t in tops]
    if ports[0]!=ports[1]:
        raise ValueError('stock top pin contract changed')
    for kind in ['start','status']:
        script=out/kind/'negative.ys'
        script.write_text(f'read_verilog -lib +/lattice/cells_sim_xo2.v\nread_verilog {out}/{kind}/converted.v\nsynth_lattice -family xo2 -top top -run begin:map_ram\nselect top\nwrite_json -selected {out}/{kind}/netlist.json\n')
        run(['yosys','-Q','-T','-s',script],out/kind/'synth.log')
        run(['/usr/bin/python3',here/'liveness.py',out/kind/'netlist.json'],out/kind/'liveness.log',1)
        failure=(out/kind/'liveness.log').read_text()
        if not ('missing data path' in failure or 'disconnected decoder start' in failure):
            raise ValueError('negative failed for unexpected reason')
    report={'qualification':False,'fit_demonstrated':False,
            'placement_performed':False,'route_performed':False,'bitstream_generated':False,
            'diagnostic_transforms':['guarded stock old-data forwarding','EFB inactive ties removed','generated PLL metadata restored'],
            'manifest':str(a.manifest),'manifest_sha256':hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
            'pins_only_lpf_sha256':hashlib.sha256((here.parents[4]/'build/sc64-open-memory/parent-full/pins-only-diagnostic.lpf').read_bytes()).hexdigest(),
            'helper_sha256':{str(x):hashlib.sha256(x.read_bytes()).hexdigest()
                for x in [here/'generate.py',here/'liveness.py',Path(__file__).resolve(),
                    tools/'memory/full.py',tools/'efb/inactive/prepare.py',tools/'oddr/preserve_pll_metadata.py']},
            'yosys_version':subprocess.check_output(['yosys','-V'],text=True).strip(),
            'sv2v_version':subprocess.check_output(['sv2v','--version'],text=True).strip(),
            'negative_rtl_disconnections':2,
            'nextpnr_sha256':hashlib.sha256(a.nextpnr.read_bytes()).hexdigest()}
    for kind in ['stock','candidate']:
        folder=out/(kind+'-map')
        run(['/usr/bin/python3',tools/'efb/inactive/prepare.py',folder/'mapped.json',folder/'efb.json','--diagnostic'],folder/'efb.log')
        run(['/usr/bin/python3',tools/'oddr/preserve_pll_metadata.py',top.parent/'vendor/lcmxo2/generated/pll_lattice_generated.v',folder/'efb.json',folder/'physical.json',folder/'pll.json'],folder/'pll.log')
        run([a.nextpnr,'--device','LCMXO2-7000HC-6TG144C','--json',folder/'physical.json',
             '--lpf',here.parents[4]/'build/sc64-open-memory/parent-full/pins-only-diagnostic.lpf',
             '--pack-only','--oddr-diagnostic','--efb-routing-diagnostic','--fifo-routing-diagnostic',
             '--write',folder/'packed.json'],folder/'pack.log')
        packed=json.loads((folder/'packed.json').read_text())
        report[kind]={'mapping':json.loads((folder/'result.json').read_text()),
                     'packed':dict(Counter(c['type'] for m in packed['modules'].values() for c in m['cells'].values()))}
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
