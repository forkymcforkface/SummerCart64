#!/usr/bin/env python3
"""Exercise diagnostic ODDRXE packing and the unchanged SC64 PLL wrapper."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('sc64',type=Path);p.add_argument('output',type=Path);p.add_argument('--nextpnr',default='/src/nextpnr/build/nextpnr-machxo2');a=p.parse_args()
root=a.sc64.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
source_paths=['fw/rtl/vendor/lcmxo2/pll.sv','fw/rtl/vendor/lcmxo2/generated/pll_lattice_generated.v','fw/project/lcmxo2/sc64.lpf']
(out/'source-hashes.json').write_text(json.dumps({s:hashlib.sha256((root/s).read_bytes()).hexdigest() for s in source_paths},indent=2)+'\n')
results={}
decl=Path(__file__).with_name('oddrxe_decl.v').read_text()
for name,source in {
 'data':decl+'module top(input inclk,data,output sdram_clk); ODDRXE d(.SCLK(inclk),.RST(1\'b0),.D0(data),.D1(1\'b0),.Q(sdram_clk)); endmodule\n',
 'sc64_pll':decl+'module top(input inclk,output sdram_clk,reset); wire clk; pll p(.inclk(inclk),.clk(clk),.sdram_clk(sdram_clk),.reset(reset)); endmodule\n',
}.items():
 w=out/name;w.mkdir();(w/'top.v').write_text(source)
 (w/'pins.lpf').write_text('LOCATE COMP "inclk" SITE "3";\nLOCATE COMP "sdram_clk" SITE "61";\nIOBUF PORT "inclk" IO_TYPE=LVCMOS33 PULLMODE=NONE;\nIOBUF PORT "sdram_clk" IO_TYPE=LVCMOS33 PULLMODE=NONE;\nFREQUENCY PORT "inclk" 50 MHz;\n')
 def run(cmd,log):
  with (w/log).open('w') as f:return subprocess.run(cmd,cwd=w,stdout=f,stderr=subprocess.STDOUT).returncode
 extra=''
 if name=='sc64_pll':extra=f' {root}/fw/rtl/vendor/lcmxo2/pll.sv {root}/fw/rtl/vendor/lcmxo2/generated/pll_lattice_generated.v'
 syn=run(['yosys','-p','read_verilog -lib +/lattice/cells_bb_xo2.v; read_verilog -sv top.v'+extra+'; synth_lattice -family xo2 -top top -json top.json'],'synth.log')
 command=[a.nextpnr,'--device','LCMXO2-7000HC-6TG144C','--json','top.json','--lpf','pins.lpf','--lpf-allow-unconstrained','--textcfg','top.config','--write','routed.json','--freq','100']
 fail=run(command,'normal-rejected.log') if syn==0 else None
 missing_attrs=None
 if name=='sc64_pll' and syn==0:
  missing_attrs=run(command+['--oddr-diagnostic'],'missing-attributes-rejected.log')
  assert missing_attrs!=0,'missing analog metadata must reject configuration'
  subprocess.run([sys.executable,str(Path(__file__).with_name('preserve_pll_metadata.py')),
   str(root/'fw/rtl/vendor/lcmxo2/generated/pll_lattice_generated.v'),str(w/'top.json'),
   str(w/'preserved.json'),str(w/'metadata.json')],check=True)
  command[command.index('top.json')]='preserved.json'
 route=run(command+['--oddr-diagnostic'],'route.log') if syn==0 else None
 pack=run(['ecppack','--input','top.config','--bit','diagnostic.bit'],'pack.log') if route==0 else None
 unpack=run(['ecpunpack','diagnostic.bit','unpacked.config'],'unpack.log') if pack==0 else None
 if unpack==0:
  text=(w/'unpacked.config').read_text()
  for item in ('IOLOGICA.MODE IDDR_ODDR','PIOA.DATAMUX_ODDR IOLDO'):
   assert item in text,item
  assert 'IOLOGICA.CLKOMUX CLK' in (w/'top.config').read_text()
  assert 'IOLOGICA.CLKOMUX INV' in text or 'IOLOGICA.CLKOMUX CLK' in text
  if name=='sc64_pll':
   routed=json.loads((w/'routed.json').read_text())['modules']['top']['cells']
   oddr=routed['p.oddrxe_sdram_clk_inst'];pio=routed['p.ob_sdram_clk_inst']
   routed_pll=[c for c in routed.values() if c['type']=='EHXPLLJ'][0]
   assert oddr['type']=='BIOLOGIC'
   assert oddr['connections']['CLK']==routed_pll['connections']['CLKOS']
   assert oddr['connections']['OPOS']==routed['$PACKER_VCC']['connections']['F']
   assert oddr['connections']['ONEG']==routed['$PACKER_GND']['connections']['F']
   assert oddr['connections']['LSR']==routed['$PACKER_GND']['connections']['F']
   assert oddr['connections']['IOLDO']==pio['connections']['IOLDO'] and not pio['connections']['I']
   netlist=json.loads((w/'preserved.json').read_text())
   pll=[c for c in netlist['modules']['top']['cells'].values() if c['type']=='EHXPLLJ'][0]
   expected=json.loads((w/'metadata.json').read_text())['attributes']
   for key in ('CLKOS_CPHASE','CLKOS_FPHASE','CLKOS_DIV','CLKOP_DIV','CLKFB_DIV'):
    expected[key]=int(pll['parameters'][key],2)-(1 if key.endswith('_DIV') else 0)
   for key,value in expected.items():
    import re
    found=re.findall(r'word: '+key+r' ([01]+)',text)
    assert len(found)==1 and int(found[0],2)==value,(key,found)
 results[name]=dict(synthesis=syn,normal_rejected=fail,missing_attributes_rejected=missing_attrs,diagnostic_route=route,pack=pack,unpack=unpack)
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
raise SystemExit(int(any(v['synthesis']!=0 or v['normal_rejected']==0 or v['diagnostic_route']!=0 or v['pack']!=0 or v['unpack']!=0 for v in results.values())))
