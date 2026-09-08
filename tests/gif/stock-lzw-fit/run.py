"""Reuse the stock-fit paired runner with this directory's LZW-only generator.

The imported runner resolves its sibling generator/gates through __file__;
all mapping, actual negatives, pin equality and packing gates remain shared.
"""
from pathlib import Path
import hashlib
import json
import sys

base=Path(__file__).resolve().parent.parent/'stock-fit/run.py'
exec(compile(base.read_text(),str(base),'exec'))
if __name__=='__main__':
    result=Path(sys.argv[5])/'result.json'
    report=json.loads(result.read_text())
    report['shared_stock_fit_helpers']={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [base,base.with_name('generate.py'),base.with_name('liveness.py')]}
    report['architecture']='raw LZW full index plane; N64 composition unimplemented'
    result.write_text(json.dumps(report,indent=2)+'\n')
