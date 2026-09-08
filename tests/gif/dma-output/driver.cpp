/* Exercise unmodified SC64 FIFO-to-memory DMA with original-GIF RTL packets.
   Delayed acknowledgements and registered FIFO data model digital interfaces;
   no SDRAM timing, FPGA fit or hardware playback is inferred. */
#include "Vdma_output.h"
#include "verilated.h"
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <vector>

struct Rig {
    Vdma_output t;
    std::vector<uint8_t> memory, input;
    size_t position=0;
    uint64_t cycles=0, writes=0;
    bool pending=false;
    unsigned delay=0, address=0, mask=0, data=0;
    explicit Rig(const std::vector<uint8_t> &bytes): memory(bytes.size()+64,0xa5), input(bytes) {
        t.reset=1; t.start=0; t.stop=1; t.ack=0;
        for(int i=0;i<8;i++)tick();
        t.reset=0;
        for(int i=0;i<8;i++)tick();
        t.stop=0;
    }
    void tick() {
        assert(++cycles<10000000);
        t.clk=0; t.ack=0;
        t.rx_empty=position==input.size() || cycles%19<4;
        t.eval();
        if(pending) {
            assert(t.request && t.write && t.mem_address==address);
            assert(t.wmask==mask && t.wdata==data);
            if(delay)delay--;
            else {
                assert(address+1<memory.size());
                if(mask&2)memory[address]=uint8_t(data>>8);
                if(mask&1)memory[address+1]=uint8_t(data);
                writes++;t.ack=1;pending=false;
            }
        } else if(t.request) {
            assert(t.write);
            pending=true;address=t.mem_address;mask=t.wmask;data=t.wdata;
            delay=unsigned(cycles%13)+2;
        }
        t.eval();
        bool read=t.rx_read;
        assert(!read || (!t.rx_empty && position<input.size()));
        t.clk=1;t.eval();
        if(read)t.rx_rdata=input[position++];
        t.eval();
    }
    void start(unsigned base) {
        t.address=base;t.length=unsigned(input.size());t.start=1;
        tick();t.start=0;
        while(!t.busy)tick();
    }
    void complete(unsigned base) {
        start(base);
        while(t.busy || pending)tick();
        assert(position==input.size());
        for(size_t i=0;i<memory.size();i++)
            assert(memory[i]==(i>=base && i<base+input.size()?input[i-base]:0xa5));
        auto previous=writes;
        for(int i=0;i<64;i++)tick();
        assert(writes==previous && !t.request);
    }
};
int main(int argc,char **argv) {
    Verilated::commandArgs(argc,argv);
    unsigned packets=0, cases=0;
    for(int a=1;a<argc;a++) {
        std::ifstream f(argv[a],std::ios::binary);assert(f);
        std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(f)),{});
        assert(bytes.size()>=192 && bytes.size()<=76992);
        Rig aligned(bytes);aligned.complete(16);
        Rig odd(bytes);odd.complete(17);
        packets++;cases+=2;
    }
    for(unsigned length: {0u,1u,2u,3u,15u,16u,17u,191u,192u,193u}) {
        std::vector<uint8_t> bytes(length);
        for(unsigned i=0;i<length;i++)bytes[i]=uint8_t(i*37+11);
        for(unsigned base: {16u,17u}) {
            Rig r(bytes);r.complete(base);cases++;
        }
    }
    for(unsigned offset=0;offset<12;offset++) {
        std::vector<uint8_t> old_bytes(4096);
        for(unsigned i=0;i<old_bytes.size();i++)old_bytes[i]=uint8_t(i*19+7);
        Rig r(old_bytes);r.start(16);
        while(!r.pending)r.tick();
        for(unsigned i=0;i<offset;i++)r.tick();
        r.t.stop=1;r.tick();r.t.stop=0;
        while(r.t.busy || r.pending)r.tick();
        auto previous=r.writes;
        for(int i=0;i<64;i++)r.tick();
        assert(r.writes==previous && !r.t.request);
        for(size_t i=0;i<r.memory.size();i++) {
            if(i<16 || i>=16+old_bytes.size())assert(r.memory[i]==0xa5);
            else assert(r.memory[i]==0xa5 || r.memory[i]==old_bytes[i-16]);
        }
        for(unsigned i=0;i<r.input.size();i++)r.input[i]=uint8_t(~old_bytes[i]);
        r.memory.assign(r.memory.size(),0xa5);r.position=0;
        r.complete(17);
        cases++;
    }
    assert(packets);
    printf("PASS original_RTL_packets=%u cases=%u exact_bytes guards parity stalls stop_drain restart\n",packets,cases);
}
