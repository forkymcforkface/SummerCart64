/* Raw-index original-GIF transport check using the shared SDRAM chip model.
   Cancellation retires all issued work before distinct source data is reused. */
#include "rig.hpp"

struct Frame { unsigned minimum; std::vector<uint8_t> data,expected; };
static void configure(Rig &r) {
    r.t.configure=1;r.tick();r.t.configure=0;r.tick();
    assert(r.t.configured&&!r.t.config_error);
}
static void start(Rig &r,const Frame &f,unsigned minimum) {
    assert(!r.t.source_busy&&!r.t.output_busy&&!r.t.decode_busy);
    std::fill(r.dram.begin()+0x40000,r.dram.begin()+0x40000+76992,0xa5);
    std::copy(f.data.begin(),f.data.end(),r.dram.begin()+0x30000);
    r.packet.clear();r.last_seen=false;
    r.t.source_length=f.data.size();r.t.minimum=minimum;r.t.bypass_lzw=0;
    r.t.frame_start=1;r.tick();r.t.frame_start=0;
}
static void finish(Rig &r,const Frame &f) {
    uint64_t deadline=r.cycles+20000000;
    bool done=false;
    do { assert(r.cycles<deadline);r.tick();done|=r.t.decode_done;assert(!r.t.error); }
    while(!done||r.t.source_busy||r.t.output_busy);
    assert(r.t.source_consumed==f.data.size()&&r.t.output_length==76800);
    assert(r.packet==f.expected);
    for(unsigned i=0;i<76800;i++)assert(r.dram[0x40000+i]==f.expected[i]);
    for(unsigned i=76800;i<76992;i++)assert(r.dram[0x40000+i]==0xa5);
}
int main(int argc,char **argv) {
    assert(argc==2);Verilated::commandArgs(argc,argv);
    std::ifstream file(argv[1],std::ios::binary);assert(file);
    unsigned count=le32(file);assert(count>=8);
    std::vector<Frame> frames;
    for(unsigned i=0;i<count;i++) {
        Frame f;f.minimum=le32(file);assert(le32(file)==76800);
        unsigned n=le32(file),e=le32(file);assert(!le32(file)&&e==76800&&n<=32768);
        f.data.resize(n);f.expected.resize(e);
        file.read(reinterpret_cast<char*>(f.data.data()),n);
        file.read(reinterpret_cast<char*>(f.expected.data()),e);assert(file);
        frames.push_back(f);
    }
    assert(frames[0].expected!=frames[1].expected);
    Rig r;r.reset();configure(r);r.traffic=true;
    for(unsigned i=0;i<count;i++) {
        start(r,frames[i],frames[i].minimum);finish(r,frames[i]);
        printf("PASS original raw frame=%u bytes=76800\n",i);fflush(stdout);
    }
    for(unsigned phase=0;phase<2;phase++)for(unsigned held=0;held<2;held++) {
        Rig c;c.reset();configure(c);start(c,frames[0],phase==0?1:frames[0].minimum);
        uint64_t deadline=c.cycles+20000000;
        if(phase==0) { while(!c.t.decode_error){assert(c.cycles<deadline);c.tick();} }
        else {
            while(!c.t.raw_output_request){assert(c.cycles<deadline);c.tick();}
            c.t.pi_active=1;
            for(unsigned i=0;i<128;i++)c.tick();
            assert(c.t.raw_output_request&&c.t.output_busy);
        }
        c.t.cancel=1;c.tick();if(!held)c.t.cancel=0;
        assert(c.t.aborting);c.t.pi_active=0;
        deadline=c.cycles+100000;
        while(!c.t.retired){assert(c.cycles<deadline);c.t.frame_start=1;c.tick();}
        c.t.frame_start=0;
        assert(!c.t.source_busy&&!c.t.output_busy&&!c.t.decode_busy&&!c.t.adapter_busy&&c.t.mux_idle);
        uint64_t writes=c.writes;
        for(unsigned i=0;i<64;i++)c.tick();
        assert(c.writes==writes&&!c.t.configured);
        c.t.cancel=0;c.tick();configure(c);start(c,frames[1],frames[1].minimum);finish(c,frames[1]);
        printf("PASS cancel phase=%u held=%u no_late_writes distinct_restart\n",phase,held);fflush(stdout);
    }
}
