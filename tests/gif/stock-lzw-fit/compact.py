"""Compose a passed compact decoder into the existing raw transport gates.

This orchestrates existing behavioral, stock mapping and area-mapping owners.
Only pack-only diagnostic netlists are emitted; there is no board output.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('compact_result',type=Path)
    p.add_argument('manifest',type=Path)
    p.add_argument('original',type=Path)
    p.add_argument('mux',type=Path)
    p.add_argument('nextpnr',type=Path)
    p.add_argument('output',type=Path)
    a=p.parse_args()
    here=Path(__file__).resolve().parent
    tools=here.parents[1]/'open-toolchain'
    out=a.output.resolve()
    if out.exists() or here.parents[1] in out.parents:
        p.error('fresh output outside tests required')
    passed=json.loads(a.compact_result.read_text())
    if passed.get('status')!='pass' or not all(k in passed for k in ['candidate','negative-count','negative-bits']):
        raise ValueError('passed compact decoder and both negative gates required')
    candidate=a.compact_result.parent/'candidate.sv'
    if digest(candidate)!=passed['generated_hashes']['candidate.sv']:
        raise ValueError('compact candidate hash differs from passed result')
    dictionaries=[Path(x) for x in passed['source_hashes'] if x.endswith('/cached_dictionary.sv')]
    if len(dictionaries)!=1:raise ValueError('one passed dictionary required')
    dictionary=dictionaries[0]
    if digest(dictionary)!=passed['source_hashes'][str(dictionary)]:
        raise ValueError('dictionary hash differs from passed result')
    out.mkdir(parents=True)
    core=out/'core';core.mkdir()
    (core/'gif_lzw_cached.sv').write_bytes(candidate.read_bytes())
    (core/'cached_dictionary.sv').write_bytes(dictionary.read_bytes())
    manifest=json.loads(a.manifest.read_text())
    top=next(Path(x) for x in manifest['command'] if x.endswith('/rtl/top.sv'))
    project=top.parents[1]/'project/lcmxo2'
    pins=here.parents[4]/'build/sc64-open-memory/parent-full/pins-only-diagnostic.lpf'
    report={'status':'running','hardware_qualified':False,'fit_demonstrated':False,
        'placement_performed':False,'route_performed':False,'bitstream_generated':False,
        'source_sha256':{str(x):digest(x) for x in [a.compact_result,candidate,dictionary,
            a.manifest,a.original,a.mux,a.nextpnr,pins,Path(__file__).resolve()]},'commands':[]}
    def run(command,log):
        command=list(map(str,command));report['commands'].append(command)
        with log.open('w') as f:
            subprocess.run(command,cwd=project,stdout=f,stderr=subprocess.STDOUT,
                check=True,timeout=900)
    try:
        run([sys.executable,'-B',here/'behavior.py',a.original,core,a.mux,out/'behavior'],out/'behavior.log')
        run([sys.executable,'-B',here/'run.py',a.manifest,core,a.mux,a.nextpnr,out/'stock'],out/'stock.log')
        run([sys.executable,'-B',tools/'area-map/run.py',out/'stock/candidate-map',project,out/'area'],out/'area.log')
        folder=out/'area/soft-carry'
        run([sys.executable,'-B',tools/'efb/inactive/prepare.py',folder/'mapped.json',folder/'efb.json','--diagnostic'],folder/'efb.log')
        run([sys.executable,'-B',tools/'oddr/preserve_pll_metadata.py',top.parent/'vendor/lcmxo2/generated/pll_lattice_generated.v',folder/'efb.json',folder/'physical.json',folder/'pll.json'],folder/'pll.log')
        run([a.nextpnr,'--device','LCMXO2-7000HC-6TG144C','--json',folder/'physical.json',
            '--lpf',pins,'--pack-only','--oddr-diagnostic','--efb-routing-diagnostic',
            '--fifo-routing-diagnostic','--write',folder/'packed.json'],folder/'pack.log')
        packed=json.loads((folder/'packed.json').read_text())
        report.update(status='pass',packed_cells=dict(Counter(c['type'] for m in packed['modules'].values() for c in m['cells'].values())),
            physical_path=str(folder/'physical.json'),physical_sha256=digest(folder/'physical.json'),
            child_results={str(x):digest(x) for x in [out/'behavior/result.json',out/'stock/result.json',out/'area/result.json']})
    except Exception as exc:
        report.update(status='failed',error=str(exc))
        raise
    finally:
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
