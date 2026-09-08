"""Extend the baseline differential driver with bounded spill-memory checks."""
from pathlib import Path
from run import replace


def generate(source, output, fault_bytes):
    code = source.read_text()
    code = replace(code, '    bool inject_error=false,read_error=false;', '''    bool inject_error=false,read_error=false;
    std::vector<uint8_t> spill(4096,0);
    bool spill_pending=false,spill_wr=false,spill_fault=false;
    unsigned spill_address=0,spill_delay=0,spill_extra_delay=0;uint8_t spill_data=0;
    uint64_t spill_reads=0,spill_writes=0,original_spill_reads=0,original_spill_writes=0;''')
    code = replace(code, '        d.eval();d.clk=1;d.eval();clock_count++;', '''        d.stack_ack=0;d.stack_error=0;
        if(d.memory_valid&&d.stack_valid)throw std::runtime_error("simultaneous memory owners");
        if(d.stack_valid){
            if(!spill_pending){spill_pending=true;spill_address=d.stack_address;spill_wr=d.stack_write;spill_data=d.stack_wdata;spill_delay=3+(clock_count%13)+spill_extra_delay;spill_extra_delay=0;}
            if(spill_address!=d.stack_address||spill_wr!=bool(d.stack_write)||spill_data!=d.stack_wdata)throw std::runtime_error("spill request changed");
            if(spill_address<512||spill_address>=4096)throw std::runtime_error("spill address bound");
            if(spill_delay)spill_delay--;
            else{
                d.stack_ack=1;d.stack_error=spill_fault;spill_fault=false;
                d.stack_rdata=spill[spill_address];
                if(spill_wr){spill_writes++;if(!d.stack_error)spill[spill_address]=spill_data;}else spill_reads++;
                spill_pending=false;
            }
        }else if(spill_pending)throw std::runtime_error("spill request dropped");
        d.eval();d.clk=1;d.eval();clock_count++;''')
    code = replace(code, 'cycles>6000000', 'cycles>6000000ull+uint64_t(limit)*120')
    code = replace(code, 'original_reads=reads;original_writes=writes;', 'original_reads=reads;original_writes=writes;original_spill_reads=spill_reads;original_spill_writes=spill_writes;')
    marker = '    std::cout<<"PASS fixtures="'
    tests = '''    const std::vector<uint8_t> spill_raw={BYTES};
    for(unsigned test=0;test<8;test++){
        d.minimum=2;d.output_limit=131841;d.start=1;d.in_valid=0;d.in_end=0;d.out_ready=1;
        tick();d.start=0;unsigned ip=0;uint64_t guard=0,cancel_clock=0;bool triggered=false;
        while(!d.done && !(triggered&&test>=2&&!d.busy)){
            if(++guard>50000000)throw std::runtime_error("spill fault watchdog");
            d.clk=0;d.in_valid=ip<spill_raw.size();d.in_end=ip==spill_raw.size();d.in_byte=ip<spill_raw.size()?spill_raw[ip]:0;d.eval();
            if(d.in_valid&&d.in_ready)ip++;
            if(d.out_valid&&d.out_byte!=0)throw std::runtime_error("spill fault prefix");
            if(!triggered&&d.stack_valid&&bool(d.stack_write)==(test%2==0)&&
               (test<6||(spill_pending&&spill_delay==0))){
                triggered=true;
                cancel_clock=clock_count;
                if(test==4||test==5)spill_extra_delay=700;
                if(test<2)spill_fault=true;else d.cancel=1;
            }
            tick();d.cancel=0;
        }
        if(!triggered||spill_pending||d.stack_valid||pending)throw std::runtime_error("spill fault did not retire");
        if(test<2&&!d.error)throw std::runtime_error("spill error lost");
        if(test>=2&&d.busy)throw std::runtime_error("spill cancel busy");
        if((test==4||test==5)&&clock_count-cancel_clock<700)throw std::runtime_error("long cancel not exercised");
        for(unsigned idle=0;idle<32;idle++){tick();if(d.stack_valid)throw std::runtime_error("late spill request");}
        const std::vector<uint8_t> tiny={4,80};
        d.minimum=2;d.output_limit=3;d.start=1;d.in_valid=0;d.in_end=0;tick();d.start=0;
        ip=0;unsigned op=0;guard=0;
        while(!d.done){
            if(++guard>100000)throw std::runtime_error("spill restart watchdog");
            d.clk=0;d.in_valid=ip<tiny.size();d.in_end=ip==tiny.size();d.in_byte=ip<tiny.size()?tiny[ip]:0;d.eval();
            if(d.in_valid&&d.in_ready)ip++;
            if(d.out_valid&&d.out_ready){if(d.out_byte!=0)throw std::runtime_error("spill restart data");op++;}
            tick();
        }
        if(d.error||op!=3)throw std::runtime_error("spill restart completion");
    }
    if(original_spill_reads||original_spill_writes)throw std::runtime_error("original unexpectedly spilled");
    if(originals!=1717||total!=1257856312ull)throw std::runtime_error("original cycle baseline changed");
    std::cout<<"SPILL original_reads="<<original_spill_reads<<" original_writes="<<original_spill_writes<<" total_reads="<<spill_reads<<" total_writes="<<spill_writes<<" faults_cancel_restart=8\\n";
'''.replace('BYTES', ','.join(map(str, fault_bytes)))
    code = replace(code, marker, tests + marker)
    (output / 'driver.cpp').write_text(code)
