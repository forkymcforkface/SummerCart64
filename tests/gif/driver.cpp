/* Original-GIF differential simulation with deterministic input/output stalls,
   finite watchdog, bounded output and cancellation/restart checks. */
#include "Vgif_lzw.h"
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
    Verilated::commandArgs(argc,argv);Vgif_lzw d;
    auto tick=[&](){d.clk=0;d.eval();d.clk=1;d.eval();};
    d.reset=1;tick();d.reset=0;
    std::ifstream f(argc>1?argv[1]:"fixtures.bin",std::ios::binary);
    if(!f)throw std::runtime_error("open fixture");
    uint32_t count=word(f),originals=word(f);uint64_t total=0,maxcycles=0,bytes=0;
    if (!originals || originals > count) throw std::runtime_error("fixture counts");
    for(uint32_t i=0;i<count;i++) {
        auto minimum=word(f),limit=word(f),n=word(f),m=word(f),err=word(f);
        std::vector<uint8_t> raw(n),expected(m);f.read((char*)raw.data(),n);f.read((char*)expected.data(),m);
        if(!f)throw std::runtime_error("short fixture");
        d.minimum=minimum;d.output_limit=limit;d.start=1;d.in_valid=0;d.in_end=0;d.out_ready=0;tick();d.start=0;
        uint32_t ip=0,op=0;uint64_t cycles=0;
        while(!d.done) {
            if(++cycles>4000000)throw std::runtime_error("watchdog frame "+std::to_string(i));
            d.clk=0;d.in_valid=ip<n && cycles%7!=0;d.in_end=ip==n;d.in_byte=ip<n?raw[ip]:0;d.out_ready=cycles%5!=0;d.eval();
            if(d.in_valid&&d.in_ready)ip++;
            if(d.out_valid&&d.out_ready) {
                if(op>=expected.size()||d.out_byte!=expected[op])throw std::runtime_error("mismatch frame "+std::to_string(i)+" byte "+std::to_string(op));
                op++;
            }
            d.clk=1;d.eval();
        }
        if(d.error!=err || (!err && op!=m))throw std::runtime_error("completion frame "+std::to_string(i));
        if(i<originals){total+=cycles;maxcycles=std::max(maxcycles,cycles);bytes+=op;}
        if(i%100==0)std::cout<<"progress "<<i<<std::endl;
    }
    for(unsigned stop=0;stop<200;stop++) {
        d.minimum=8;d.output_limit=76800;d.start=1;d.in_end=0;tick();d.start=0;
        for(unsigned j=0;j<stop;j++){d.in_valid=1;d.in_byte=0;d.out_ready=j%3;tick();}
        d.cancel=1;tick();d.cancel=0;
        if(d.busy||d.out_valid||d.error)throw std::runtime_error("cancel");
    }
    std::cout<<"PASS fixtures="<<count<<" original_frames="<<originals<<" bytes="<<bytes<<" original_cycles="<<total<<" max_frame_cycles="<<maxcycles<<" cancel_cases=200\n";
}
