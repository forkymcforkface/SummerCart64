#!/usr/bin/env python3
"""Negative guards against untimed, unconstrained or active-PLL substitutions."""
import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);p.add_argument('--nextpnr',default='/src/nextpnr/build/nextpnr-machxo2');a=p.parse_args()
w=a.evidence.resolve()/'sc64_pll';base=json.loads((w/'preserved.json').read_text());results={}
for name in ('wb_enabled','wb_nonzero','pllreset_enabled','missing_icp','missing_lpf','unconstrained_output'):
 j=json.loads(json.dumps(base));pll=[c for c in j['modules']['top']['cells'].values() if c['type']=='EHXPLLJ'][0]
 if name=='wb_enabled':pll['parameters']['PLL_USE_WB']='ENABLED'
 if name=='wb_nonzero':pll['connections']['PLLADDR2']=['1']
 if name=='pllreset_enabled':pll['parameters']['PLLRST_ENA']='ENABLED'
 if name=='missing_icp':del pll['attributes']['ICP_CURRENT']
 if name=='missing_lpf':del pll['attributes']['LPF_RESISTOR']
 (w/(name+'.json')).write_text(json.dumps(j)+'\n')
 pins=(w/'pins.lpf').read_text()
 if name=='unconstrained_output':pins='\n'.join(x for x in pins.splitlines() if not('LOCATE' in x and 'sdram_clk' in x))+'\n'
 (w/(name+'.lpf')).write_text(pins)
 with (w/(name+'.log')).open('w') as f:
  code=subprocess.run([a.nextpnr,'--device','LCMXO2-7000HC-6TG144C','--json',name+'.json','--lpf',name+'.lpf','--lpf-allow-unconstrained','--oddr-diagnostic','--textcfg',name+'.config'],cwd=w,stdout=f,stderr=subprocess.STDOUT).returncode
 assert code!=0,name
 results[name]=code
with (w/'reload-rejected.log').open('w') as f:
 code=subprocess.run([a.nextpnr,'--device','LCMXO2-7000HC-6TG144C','--json','routed.json',
  '--no-pack','--no-place','--no-route','--textcfg','reload.config'],cwd=w,stdout=f,stderr=subprocess.STDOUT).returncode
assert code!=0,'reloaded JSON cannot silently preserve diagnostic opt-in'
results['reload_without_opt_in']=code
(a.evidence/'negative-results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
