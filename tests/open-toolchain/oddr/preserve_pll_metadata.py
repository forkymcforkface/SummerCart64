#!/usr/bin/env python3
"""Preserve the generated wrapper's explicit PLL analog synthesis attributes.

This narrow metadata bridge rejects ambiguity and conflicting existing values.
It modifies diagnostic JSON only; RTL and numeric source values are unchanged.
"""
import argparse,hashlib,json,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('wrapper',type=Path);p.add_argument('netlist',type=Path);p.add_argument('output',type=Path);p.add_argument('manifest',type=Path);a=p.parse_args()
raw=a.wrapper.read_bytes();text=raw.decode();j=json.loads(a.netlist.read_text())
values={}
for key in ('ICP_CURRENT','LPF_RESISTOR'):
 matches=re.findall(r'/\*\s*synthesis\s+'+key+r'="(\d+)"\s*\*/',text)
 assert len(matches)==1,(key,matches)
 value=int(matches[0]);assert 0<=value<(32 if key=='ICP_CURRENT' else 128)
 values[key]=value
cells=[(name,c) for m in j['modules'].values() for name,c in m.get('cells',{}).items() if c['type']=='EHXPLLJ']
assert len(cells)==1,'metadata bridge requires exactly one generated PLL'
name,cell=cells[0]
assert 'PLLInst_0' in name,'unexpected generated PLL instance'
for key,value in values.items():
 existing=cell.setdefault('attributes',{}).get(key)
 assert existing is None or int(existing,2)==value,(key,existing)
 cell['attributes'][key]=format(value,'032b')
a.output.write_text(json.dumps(j)+'\n')
a.manifest.write_text(json.dumps(dict(wrapper=str(a.wrapper),wrapper_sha256=hashlib.sha256(raw).hexdigest(),input_json_sha256=hashlib.sha256(a.netlist.read_bytes()).hexdigest(),cell=name,attributes=values),indent=2)+'\n')
