"""Compare mapping options from a passed guarded stock integration checkpoint.

Only logic mapping options differ. Existing RAM forwarding, source conversion
and physical memory contracts remain prerequisites. Counts are area evidence,
not a functional, timing, configuration or hardware qualification.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline',type=Path)
    p.add_argument('project',type=Path)
    p.add_argument('output',type=Path)
    a=p.parse_args()
    baseline=a.baseline.resolve()
    out=a.output.resolve()
    if out.exists() or out.is_relative_to(Path(__file__).resolve().parents[2]):
        p.error('fresh output outside tests required')
    prior=json.loads((baseline/'result.json').read_text())
    if prior['status']!='passed' or prior['address_implications']!=8:
        raise ValueError('passed guarded mapping required')
    original=(baseline/'map.ys').read_text()
    converted=Path(re.findall(r'^read_verilog ([^ -]\S+)$',original,re.M)[0])
    if hashlib.sha256(converted.read_bytes()).hexdigest()!=prior['converted_sha256']:
        raise ValueError('source conversion differs from passed baseline')
    anchor='synth_lattice -family xo2 -top top -run map_ffram:'
    if original.count(anchor)!=1:
        raise ValueError('mapping continuation anchor changed')
    out.mkdir(parents=True)
    result={'hardware_qualified':False,'functional_equivalence_proven':False,'variants':{}}
    try:
        for name,option in [('baseline',''),('soft-carry','-noccu2'),
                            ('soft-compare','-cmp2softlogic'),('soft-both','-noccu2 -cmp2softlogic')]:
            folder=out/name
            folder.mkdir()
            (folder/'forward.json').write_bytes((baseline/'forward.json').read_bytes())
            script=original.replace(str(baseline)+'/',str(folder)+'/')
            script=script.replace(anchor,'synth_lattice -family xo2 -top top '+option+' -run map_ffram:')
            path=folder/'map.ys'
            path.write_text(script)
            with (folder/'map.log').open('w') as log:
                subprocess.run(['yosys','-Q','-T','-s',str(path)],cwd=a.project,
                               stdout=log,stderr=log,check=True,timeout=600)
            top=json.loads((folder/'mapped.json').read_text())['modules']['top']
            counts=dict(Counter(c['type'] for c in top['cells'].values()))
            ram=json.loads((folder/'mapped-ram.json').read_text())['modules']['top']['cells']
            shape=sorted((c['type'],json.dumps(c['parameters'],sort_keys=True)) for c in ram.values()
                         if c['type'] in ['DP8KC','FIFO8KB','TRELLIS_DPR16X4'])
            final_shape=sorted((c['type'],json.dumps(c['parameters'],sort_keys=True)) for c in top['cells'].values()
                              if c['type'] in ['DP8KC','FIFO8KB','TRELLIS_DPR16X4'])
            if name=='baseline':
                expected=shape
                expected_final=final_shape
                if counts!=prior['cells']:
                    raise ValueError('fresh baseline mapping differs')
            elif shape!=expected or final_shape!=expected_final:
                raise ValueError('physical RAM shapes or parameters differ')
            result['variants'][name]={'options':option,'cells':counts,
                'prepack_logic_units':counts.get('LUT4',0)+2*counts.get('CCU2D',0)+6*counts.get('TRELLIS_DPR16X4',0)}
        result.update(status='pass',yosys=subprocess.check_output(['yosys','-V'],text=True).strip(),
            source_hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in
                [baseline/'map.ys',baseline/'forward.json',baseline/'result.json',converted,
                 Path(shutil.which('yosys')),Path(__file__)]})
    except Exception as exc:
        result.update(status='failed',error=str(exc))
        raise
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
