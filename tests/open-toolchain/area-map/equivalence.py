"""Prove mapped arithmetic shapes extracted from an actual guarded checkpoint.

This is a combinational operator-shape gate. It does not prove the surrounding
mapped sequential fabric, physical hard blocks, initialization or timing.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import shutil


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('area_result',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    prior,out=args.area_result.resolve(),args.output.resolve()
    if out.exists() or Path(__file__).resolve().parents[2] in out.parents:
        raise ValueError('Output must be new and outside tests')
    status=json.loads((prior/'result.json').read_text())
    if status['status']!='pass':raise ValueError('Requires passed area comparison')
    binary=Path(shutil.which('yosys'))
    binary_hash=hashlib.sha256(binary.read_bytes()).hexdigest()
    if status['source_hashes'].get(str(binary))!=binary_hash:
        raise ValueError('Yosys executable differs from the passed area mapping')
    checkpoint=prior/'baseline/forward.json'
    checkpoint_bytes=checkpoint.read_bytes()
    checkpoint_hash=hashlib.sha256(checkpoint_bytes).hexdigest()
    recorded=[digest for path,digest in status['source_hashes'].items() if Path(path).name=='forward.json']
    if len(recorded)!=1 or checkpoint_hash!=recorded[0]:
        raise ValueError('Checkpoint differs from the passed area mapping or lacks unique provenance')
    top=json.loads(checkpoint_bytes)['modules']['top']
    groups={}
    for name,cell in top['cells'].items():
        if cell['type']!='$alu':continue
        signature=json.dumps([cell['parameters'],cell['port_directions'],
                              {p:len(v) for p,v in cell['connections'].items()}],sort_keys=True)
        groups.setdefault(signature,[]).append(name)
    if not groups:raise ValueError('No actual arithmetic operators')
    datadir=Path(subprocess.check_output(['yosys-config','--datdir'],text=True).strip())
    model=datadir/'lattice/cells_sim_xo2.v'
    out.mkdir(parents=True)
    result={'status':'running','functional_equivalence_proven':False,'hardware_qualified':False,
            'scope':'all actual $alu parameter/port shapes with independent inputs; not surrounding netlist'}
    def run(script,name,negative=False):
        path=out/(name+'.ys');path.write_text(script+'\n')
        with (out/(name+'.log')).open('w') as log:
            completed=subprocess.run(['yosys','-Q','-T','-s',str(path)],stdout=log,stderr=subprocess.STDOUT,timeout=180)
        text=(out/(name+'.log')).read_text()
        if negative:
            if completed.returncode==0 or 'proof did fail' not in text:
                raise ValueError('Negative failed for wrong reason or passed')
        elif completed.returncode:raise ValueError('Tool failure: '+name)
        return text
    try:
        module={'attributes':{'top':'1'},'ports':{},'cells':{},'netnames':{}}
        next_bit=2;inventory=[]
        for index,(signature,names) in enumerate(sorted(groups.items())):
            parameters,directions,widths=json.loads(signature)
            connections={}
            for port,width in sorted(widths.items()):
                bits=list(range(next_bit,next_bit+width));next_bit+=width
                name=f'op{index}_{port}'
                module['ports'][name]={'direction':directions[port],'bits':bits}
                module['netnames'][name]={'hide_name':0,'bits':bits,'attributes':{}}
                connections[port]=bits
            module['cells'][f'op{index}']={'hide_name':0,'type':'$alu','parameters':parameters,
                                         'attributes':{},'port_directions':directions,'connections':connections}
            inventory.append({'operator':index,'parameters':parameters,'source_cells':names})
        (out/'operators.json').write_text(json.dumps({'modules':{'top':module}}))
        counts={}
        for label,option in [('default',''),('soft','-noccu2')]:
            mapped=out/(label+'.json')
            run(f'read_json {out}/operators.json; synth_lattice -family xo2 -top top {option}; '
                f'check -assert; write_json {mapped}',label+'-map')
            mapped_top=json.loads(mapped.read_text())['modules']['top']
            counts[label]=dict(Counter(c['type'] for c in mapped_top['cells'].values()))
            if set(counts[label])-{'LUT4','CCU2D','$scopeinfo'}:
                raise ValueError('Unexpected non-combinational mapped cells')
            single=out/(label+'-top.json')
            single.write_text(json.dumps({'modules':{'top':mapped_top}}))
            run(f'read_verilog -DNO_INCLUDES {model}; read_json {single}; hierarchy -check -top top; flatten; proc; opt; '
                f'rename top {label}; write_json {out}/{label}-flat.json',label+'-flatten')
            flat=out/(label+'-flat.json')
            content=json.loads(flat.read_text())['modules'][label]
            content['netnames']={name:net for name,net in content['netnames'].items() if name in content['ports']}
            flat.write_text(json.dumps({'modules':{label:content}}))
        proof=(f'read_json {out}/default-flat.json; read_json {out}/soft-flat.json; '
               'miter -equiv default soft miter; hierarchy -top miter; flatten; '
               'sat -verify -prove trigger 0')
        text=run(proof,'proof')
        if 'SAT proof finished - no model found: SUCCESS!' not in text:
            raise ValueError('Positive SAT proof lacks explicit success diagnostic')
        negative=json.loads((out/'soft-top.json').read_text())
        cells=negative['modules']['top']['cells']
        name=next(n for n,c in cells.items() if c['type']=='LUT4')
        init=cells[name]['parameters']['INIT']
        cells[name]['parameters']['INIT']=''.join('1' if b=='0' else '0' for b in init)
        (out/'negative-top.json').write_text(json.dumps(negative))
        run(f'read_verilog -DNO_INCLUDES {model}; read_json {out}/negative-top.json; hierarchy -check -top top; flatten; proc; opt; '
            f'rename top soft; write_json {out}/negative-flat.json','negative-flatten')
        flat=out/'negative-flat.json'
        content=json.loads(flat.read_text())['modules']['soft']
        content['netnames']={name:net for name,net in content['netnames'].items() if name in content['ports']}
        flat.write_text(json.dumps({'modules':{'soft':content}}))
        run(proof.replace('soft-flat.json','negative-flat.json'),'negative-proof',True)
        if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=checkpoint_hash:
            raise ValueError('Checkpoint changed during the proof')
        model_files=[model,*[datadir/'lattice'/n for n in ['common_sim.vh','ccu2d_sim.vh','arith_map_ccu2d.v','cells_map_trellis.v']]]
        result.update(status='pass',arithmetic_shape_equivalence_proven=True,
                      original_alu_cells=sum(len(v) for v in groups.values()),unique_shapes=len(groups),
                      compared_output_bits=sum(len(p['bits']) for p in module['ports'].values() if p['direction']=='output'),
                      shapes=inventory,mapped_cells=counts,negative_mutated_cell=name,
                      source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                     [checkpoint,prior/'result.json',Path(__file__),binary,*model_files]},
                      yosys=subprocess.check_output(['yosys','-V'],text=True).strip(),
                      proof_tail=text.strip().splitlines()[-5:])
    except Exception as exc:
        result.update(status='failed',error=str(exc));raise
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
