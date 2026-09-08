/* Original-GIF differential simulation with deterministic input/output stalls,
   finite watchdog, bounded output and cancellation/restart checks. */
#include "Vgif_lzw_cached.h"
#include "verilated.h"
#include <fstream>
#include <vector>
#include <iostream>
#include <algorithm>
#include <stdexcept>
static uint32_t word(std::ifstream &f) {
    unsigned char b[4];
    if (!f.read((char *)b, sizeof b)) throw std::runtime_error("short fixture word");
    return uint32_t(b[0]) | uint32_t(b[1]) << 8 |
           uint32_t(b[2]) << 16 | uint32_t(b[3]) << 24;
}
int main(int argc,char**argv) {
    Verilated::commandArgs(argc,argv);Vgif_lzw_cached d;
    std::vector<uint32_t> dictionary(4096,0);
    bool pending=false;unsigned delay=0,key=0;bool wr=false;uint32_t value=0;
    uint64_t clock_count=0,reads=0,writes=0;
    bool inject_error=false,read_error=false;
    auto tick=[&](){
        d.clk=0;d.eval();d.memory_ack=0;d.memory_error=0;
        if(d.memory_valid){
            if(!pending){pending=true;key=d.memory_key;wr=d.memory_write;value=d.memory_wdata;delay=3+(key&7);}
            if(key!=d.memory_key||wr!=bool(d.memory_write)||value!=d.memory_wdata)throw std::runtime_error("memory request changed");
            if(delay)delay--;
            else if(clock_count%1000>=40){
                d.memory_ack=1;d.memory_rdata=dictionary[key];
                d.memory_error=inject_error||(read_error&&!wr);inject_error=false;
                if(d.memory_error)read_error=false;
                if(wr){if(!d.memory_error)dictionary[key]=value;writes++;}else reads++;
                pending=false;
            }
        }else if(pending)throw std::runtime_error("memory request dropped");
        d.eval();d.clk=1;d.eval();clock_count++;
    };
    d.reset=1;tick();d.reset=0;
    std::ifstream f(argc>1?argv[1]:"fixtures.bin",std::ios::binary);
    if(!f)throw std::runtime_error("open fixture");
    uint32_t count=word(f),originals=word(f);uint64_t total=0,maxcycles=0,bytes=0,original_reads=0,original_writes=0;
    if (!originals || originals > count) throw std::runtime_error("fixture counts");
    for(uint32_t i=0;i<count;i++) {
        auto minimum=word(f),limit=word(f),n=word(f),m=word(f),err=word(f);
        std::vector<uint8_t> raw(n),expected(m);f.read((char*)raw.data(),n);f.read((char*)expected.data(),m);
        if(!f)throw std::runtime_error("short fixture");
        d.minimum=minimum;d.output_limit=limit;d.start=1;d.in_valid=0;d.in_end=0;d.out_ready=0;tick();d.start=0;
        uint32_t ip=0,op=0;uint64_t cycles=0;
        while(!d.done) {
            if(++cycles>6000000)throw std::runtime_error("watchdog frame "+std::to_string(i));
            d.clk=0;d.in_valid=ip<n && cycles%7!=0;d.in_end=ip==n;d.in_byte=ip<n?raw[ip]:0;d.out_ready=cycles%5!=0;d.eval();
            if(d.in_valid&&d.in_ready)ip++;
            if(d.out_valid&&d.out_ready) {
                if(op>=expected.size()||d.out_byte!=expected[op])throw std::runtime_error("mismatch frame "+std::to_string(i)+" byte "+std::to_string(op));
                op++;
            }
            tick();
        }
        if(d.error!=err || (!err && op!=m))throw std::runtime_error("completion frame "+std::to_string(i));
        if(i<originals){total+=cycles;maxcycles=std::max(maxcycles,cycles);bytes+=op;}
        if(i+1==originals){original_reads=reads;original_writes=writes;}
        if(i%100==0)std::cout<<"progress "<<i<<std::endl;
    }
    for(unsigned stop=0;stop<200;stop++) {
        d.minimum=8;d.output_limit=76800;d.start=1;d.in_end=0;tick();d.start=0;
        for(unsigned j=0;j<(stop*37)%2000;j++){d.in_valid=1;d.in_byte=0;d.out_ready=j%3;tick();}
        d.cancel=1;tick();d.cancel=0;
        unsigned drain=0;while(d.busy){tick();if(++drain>1000)throw std::runtime_error("cancel drain");}
        if(d.out_valid||d.error||pending)throw std::runtime_error("cancel");
    }
    std::vector<uint8_t> read_fault_stream;
    uint32_t packed=0;unsigned packed_bits=0,code_width=9,next_code=258;
    auto append_code=[&](unsigned code){
        packed|=code<<packed_bits;packed_bits+=code_width;
        while(packed_bits>=8){read_fault_stream.push_back(uint8_t(packed));packed>>=8;packed_bits-=8;}
    };
    append_code(256);
    for(unsigned i=0;i<1024;i++){
        append_code(i&255);
        if(i){next_code++;if(next_code==(1u<<code_width))code_width++;}
    }
    append_code(258);append_code(257);
    if(packed_bits)read_fault_stream.push_back(uint8_t(packed));
    for(unsigned mode=0;mode<4;mode++) {
        const std::vector<uint8_t> tiny={4,80};
        const auto &raw=mode==3?read_fault_stream:tiny;
        d.minimum=mode==3?8:2;d.output_limit=mode==3?1026:3;d.start=1;d.in_end=0;d.in_valid=0;d.out_ready=1;
        tick();d.start=0;unsigned ip=0,guard=0;bool cancelling=false;
        inject_error=mode==0;read_error=mode==3;
        while(!d.done && !(cancelling&&!d.busy)) {
            if(++guard>2000000)throw std::runtime_error("memory fault/cancel watchdog");
            d.clk=0;d.in_valid=ip<raw.size();d.in_end=ip==raw.size();d.in_byte=ip<raw.size()?raw[ip]:0;d.eval();
            if(d.in_valid&&d.in_ready)ip++;
            if(mode==1&&!cancelling&&d.memory_valid){d.cancel=1;cancelling=true;}
            tick();d.cancel=0;
        }
        if((mode==0||mode==3)&&!d.error)throw std::runtime_error("memory error lost");
        if(mode==1&&(pending||d.memory_valid||d.busy))throw std::runtime_error("cancel did not drain memory");
        if(mode==2&&d.error)throw std::runtime_error("restart after memory error/cancel");
    }
    std::cout<<"PASS fixtures="<<count<<" original_frames="<<originals<<" bytes="<<bytes<<" original_cycles="<<total<<" max_frame_cycles="<<maxcycles<<" cancel_cases=200 memory_error_cancel_restart=4 original_memory_reads="<<original_reads<<" original_memory_writes="<<original_writes<<" total_memory_reads="<<reads<<" total_memory_writes="<<writes<<"\n";
}
