#!/usr/bin/env python3
"""A missing converter must leave an explicit failed status, never a traceback-only run."""
import argparse,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
missing=a.output.resolve().parent/'nonexistent-sv2v-for-regression'
assert not missing.exists()
code=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'probe.py'),
 str(a.root),str(a.output),'--frontend','sv2v','--sv2v',str(missing)],timeout=30).returncode
status=json.loads((a.output/'status.json').read_text())
assert code==127 and status['prerequisite_exit']==127 and status['failed_stage']=='sv2v-version'
assert status['conversion_exit'] is None and status['synthesis_exit'] is None
assert not status['hardware_qualified'] and not status['bitstream_generated']
assert (a.output/'sv2v-version.log').is_file() and not (a.output/'sc64.json').exists()
print('PASS missing executable returns127 and records failed prerequisite status')
