"""Run the actual-arbiter finite fairness matrix with a frozen four-client mux."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mux', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    rtl = here.parents[2]/'fw/rtl'
    out = args.output.resolve()
    if out.exists() or here.parent.parent in out.parents:
        raise ValueError('Output must be new and outside tests')
    out.mkdir(parents=True)
    result = {'status': 'running', 'hardware_qualified': False}
    try:
        inputs = [rtl/'memory/mem_bus.sv',rtl/'n64/n64_scb.sv',rtl/'memory/memory_arbiter.sv',
                  args.mux.resolve(),here/'fairness.sv',here/'driver.cpp']
        with (out/'compile.log').open('w') as log:
            subprocess.run(['verilator','--cc','--exe','--build','-j','2','--top-module','fairness',
                            '--Mdir',str(out/'obj'),*map(str,inputs)],
                           stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        with (out/'observations.jsonl').open('w') as log:
            subprocess.run([str(out/'obj/Vfairness')],stdout=log,stderr=subprocess.STDOUT,
                           check=True,timeout=120)
        observations = [json.loads(line) for line in (out/'observations.jsonl').read_text().splitlines()]
        if len(observations)!=54:
            raise ValueError('Incomplete fairness matrix')
        result.update(status='pass',cases=observations,
                      source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs+[Path(__file__)]},
                      verilator=subprocess.check_output(['verilator','--version'],text=True).strip())
    except Exception as exc:
        result.update(status='failed',error=str(exc))
        raise
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
