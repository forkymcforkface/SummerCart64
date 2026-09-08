"""Require an incorrect MCU ACK-owner mutation to fail the real scoreboard."""
import pathlib
import hashlib
import json
import subprocess
import sys


def main():
    out = pathlib.Path(sys.argv[1]).resolve()
    here = pathlib.Path(__file__).resolve().parent
    source = (out/'gif_transport_mcu_mux.sv').read_text()
    anchor = 'mcu.ack=state==ACTIVE&&owner==3&&memory.ack;'
    assert source.count(anchor)==1
    path = out/'wrong-ack.sv'
    with path.open('x') as stream:
        stream.write(source.replace(anchor,anchor.replace('owner==3','owner==2')))
    command = ['verilator','--cc','--exe','--build','-j','4',
               '--top-module','top','--Mdir',str(out/'negative-obj'),
               str(here.parents[2]/'fw/rtl/memory/mem_bus.sv'),str(path),
               str(out/'stock_memory_slice.sv'),str(here/'top.sv'),str(here/'driver.cpp')]
    result = subprocess.run(command,capture_output=True,text=True,timeout=120)
    (out/'negative-compile.log').write_text(result.stdout+result.stderr)
    assert result.returncode==0
    result = subprocess.run([str(out/'negative-obj/Vtop')],capture_output=True,text=True,timeout=30)
    (out/'negative.log').write_text(result.stdout+result.stderr)
    assert result.returncode==-6 and 'mask==(1u<<owner)' in result.stderr
    print('PASS incorrect MCU ACK routing rejected by scoreboard (SIGABRT)')
    positive = (out/'results.log').read_text()
    checks = ['PASS stock512 write with three saturated peers',
              'PASS pending GIF requests retain admission through cancel drain until their ACKs',
              'PASS GIF cancel preserves512 MCU reads; GIF idle survives1000 stalled MCU cycles',
              'PASS GIF restart fairness and held ACK gap',
              'PASS in-flight GIF request and held ACK block GIF retirement until drained']
    assert all(text in positive for text in checks)
    assert 'SUCCESS' in (out/'width-proof.log').read_text()
    vendor = here.parents[2]
    sources = [here/name for name in ['generate.py','driver.cpp','top.sv','run.sh','synth.py','negative.py']]
    sources += [here.parent/'transport-mux/run.py',
                here.parent/'sc64-transport-abort/gif_transport_mux.sv',
                vendor/'fw/rtl/mcu/mcu_top.sv',vendor/'fw/rtl/memory/mem_bus.sv']
    hashes = lambda paths: {str(path.relative_to(vendor) if path.is_relative_to(vendor)
                               else path.name):hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in paths}
    versions = {'python':sys.version}
    for name,command in [('verilator',['verilator','--version']),('yosys',['yosys','-V'])]:
        version = subprocess.run(command,capture_output=True,text=True,timeout=10,check=True)
        versions[name]=version.stdout.strip()
    manifest = {'hardware_qualified':False,'source_sha256':hashes(sources),
                'generated_sha256':hashes([out/'gif_transport_mcu_mux.sv',out/'stock_memory_slice.sv']),
                'tools':versions,'gates':{'positive':{'status':'PASS','checks':checks},
                'negative':{'status':'PASS','expected_returncode':-6,
                            'diagnostic':'mask==(1u<<owner)'},
                'width_equivalence':{'status':'PASS','diagnostic':'SUCCESS'},
                'synthesis':{'status':'PASS','result':json.loads((out/'synth-result.json').read_text())}}}
    with (out/'result.json').open('x') as stream:
        stream.write(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':
    main()
