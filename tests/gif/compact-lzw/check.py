"""Check local width invariants, without claiming whole-decoder equivalence.

These recurrence and combinational gates assume the documented active-state
bounds. Full malformed-input and lifecycle verification belongs to run.py.
"""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    out=args.output.resolve()
    if out.exists() or Path(__file__).resolve().parents[2] in out.parents:
        raise ValueError('Output must be new and outside tests')
    out.mkdir(parents=True)
    transitions=0
    for available in range(20):
        for width in range(3,13):
            if available<width:
                assert available<=11 and available+8<=19
            else:
                assert 0<=available-width<=16
            transitions+=1
    for size in range(513):
        assert size<1024
        if size<512:assert size+1<=512
        if size:assert size-1<512
    for minimum in range(2,9):
        assert (1<<minimum)+1<512
    proof='''module proof(input [18:0] reservoir,input [7:0] byte_value,
input [4:0] available,input [3:0] width,output good);
wire [23:0] old_fill={5'd0,reservoir}|({16'd0,byte_value}<<available);
wire [SMALL:0] new_fill=SMALLCAST'(reservoir)|(BYTECAST'(byte_value)<<available);
wire [23:0] old_shift={5'd0,reservoir}>>width;
wire [18:0] new_shift=reservoir>>width;
wire [11:0] old_code=12'({5'd0,reservoir}&((24'd1<<width)-24'd1));
wire [11:0] new_code=reservoir[11:0]&((12'd1<<width)-12'd1);
assign good=(available>11 || old_fill==24'(new_fill)) &&
            (old_shift=={5'd0,new_shift}) && old_code==new_code;
endmodule
'''
    result={'status':'running','available_transitions':transitions,'scope':'local invariants and combinational datapath only'}
    try:
        for name,bits in [('positive',19),('negative',18)]:
            text=proof.replace('SMALLCAST',str(bits)).replace('BYTECAST',str(bits)).replace('SMALL',str(bits-1))
            path=out/(name+'.sv');path.write_text(text)
            with (out/(name+'.log')).open('w') as log:
                completed=subprocess.run(['yosys','-Q','-p',f'read_verilog -sv {path}; prep -top proof; sat -verify -prove good 1 -show-inputs'],
                                         stdout=log,stderr=subprocess.STDOUT,timeout=30)
            log=(out/(name+'.log')).read_text()
            if name=='positive' and completed.returncode:
                raise ValueError('Local datapath proof failed')
            if name=='negative' and (completed.returncode==0 or 'proof did fail' not in log):
                raise ValueError('Undersized reservoir negative did not fail')
        counter='''module proof(input [31:0] emitted,limit,input push,output good);
wire domain=emitted<=limit && limit<=76800 && (!push || emitted<limit);
wire [31:0] old_difference=limit-emitted;
wire [BITS:0] difference=COUNT'(limit)-COUNT'(emitted);
wire [31:0] old_next=emitted+{31'd0,push};
wire [BITS:0] next_value=COUNT'(emitted)+COUNT'(push);
assign good=!domain || (old_difference==32'(difference) && old_next==32'(next_value));
endmodule
'''
        for name,bits in [('counter',17),('counter-negative',16)]:
            path=out/(name+'.sv')
            path.write_text(counter.replace('BITS',str(bits-1)).replace('COUNT',str(bits)))
            with (out/(name+'.log')).open('w') as log:
                completed=subprocess.run(['yosys','-Q','-p',f'read_verilog -sv {path}; prep -top proof; sat -verify -prove good 1 -show-inputs'],
                                         stdout=log,stderr=subprocess.STDOUT,timeout=30)
            text=(out/(name+'.log')).read_text()
            if name=='counter' and completed.returncode:
                raise ValueError('Counter recurrence proof failed')
            if name=='counter-negative' and (completed.returncode==0 or 'proof did fail' not in text):
                raise ValueError('Undersized counter negative did not fail')
        result['status']='pass'
    except Exception as exc:
        result.update(status='failed',error=str(exc));raise
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
