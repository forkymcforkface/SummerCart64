#!/usr/bin/env python3
"""Check interface/inout lowering and literal high-Z without accepting X as Z."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--sv2v',default='sv2v');a=p.parse_args()
s=Path(__file__).resolve().parent;w=a.output.resolve();w.mkdir(parents=True,exist_ok=False)
if any(c.isspace() or c in '\";\\' for c in str(s)+str(w)):
 p.error('mount fixture sources and outputs at simple POSIX paths')
def run(command,name):
 with (w/(name+'.log')).open('w') as log:
  return subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=60).returncode
results={}
for name,options in [('slang-default',''),('slang-best-effort','--best-effort-hierarchy'),('slang-keep','--keep-hierarchy')]:
 code=run(['yosys','-m','slang','-Q','-T','-p',f'read_slang --top top {options} {s}/boundary.sv'],name)
 assert code!=0 and 'interface port on kept module boundary must be a modport' in (w/(name+'.log')).read_text()
 results[name]=code
with (w/'converted.v').open('w') as converted,(w/'conversion.log').open('w') as log:
 code=subprocess.run([a.sv2v,str(s/'boundary.sv')],stdout=converted,stderr=log,timeout=60).returncode
assert code==0
results['conversion']=code
results['conversion_sha256']=hashlib.sha256((w/'converted.v').read_bytes()).hexdigest()
for name,command in [('native-converted',f'read_verilog {w}/converted.v'),('slang-z',f'read_slang --top top {s}/highz.v'),('native-z',f'read_verilog {s}/highz.v')]:
 code=run(['yosys','-m','slang','-Q','-T','-p',command+f'; hierarchy -check -top top; proc; flatten; opt_expr; opt_clean; write_json {w}/{name}.json'],name)
 assert code==0
 module=json.loads((w/(name+'.json')).read_text())['modules']['top']
 floating=module['ports']['floating']['bits']
 assert floating==(['x'] if name=='slang-z' else ['z']),(name,floating)
 if name=='native-converted':
  mux=[c for c in module['cells'].values() if c['type']=='$mux']
  assert len(mux)==1
  con=mux[0]['connections']
  assert con['A']==['z'] and con['B']==['0']
  assert con['S']==module['ports']['enable']['bits'] and con['Y']==module['ports']['pad']['bits']
 results[name]={'exit':code,'floating':floating}
results['sv2v_version']=subprocess.check_output([a.sv2v,'--version'],text=True).strip()
(w/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
