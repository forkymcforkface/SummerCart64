/* Scoreboard delayed memory ACKs, stock MCU bursts and independent GIF admission.
 * All comparisons operate at the mem_bus boundary; no device timing is modeled. */
#include "Vtop.h"
#include <verilated.h>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>

struct Rig {
    Vtop d;
    unsigned cycles=0,due=0,release=0,owner=0;
    bool pending=false,responding=false,stall=false;
    uint32_t address=0;
    uint16_t data=0;
    bool write=false;
    std::array<unsigned,4> completed{};
    std::array<uint16_t,512> ram{};
    std::vector<unsigned> grants;
    unsigned gif_after_cancel=0;
    bool cancel_mark=false;
    void tick() {
        assert(++cycles<200000);
        d.clk=0;
        if(responding && cycles==release) {d.ack=0;responding=false;}
        if(pending && cycles==due && !stall) {
            d.ack=1;d.rdata=address>=0x1000?ram[(address-0x1000)/2]:uint16_t(address^0x5a5a);
            pending=false;responding=true;release=cycles+3;
            if(write && address>=0x1000)ram[(address-0x1000)/2]=data;
        }
        d.eval();
        if(d.ack && cycles==due) {
            assert(d.request);
            unsigned mask=d.acks|(d.mcu_ack?8:0);
            assert(mask==(1u<<owner));
            if(owner<3) {
                assert((owner==0?d.r0:owner==1?d.r1:d.r2)==d.rdata);
                if(cancel_mark)++gif_after_cancel;
            }
            ++completed[owner];
            grants.push_back(owner);
        }
        if(!d.ack)assert(d.acks==0&&!d.mcu_ack);
        d.clk=1;d.eval();
        if(d.request && !pending && !responding) {
            address=d.bus_address;data=d.wdata;write=d.write;
            assert(d.wmask==3);
            owner=address>=0x1000?3:address==0x100?0:address==0x200?1:2;
            assert(owner==3?(address<0x1400&&!(address&1)):
                   address==(owner+1)*0x100);
            pending=true;due=cycles+2+(cycles%11);
        } else if(pending) {
            assert(d.request&&d.bus_address==address&&d.write==write&&d.wdata==data);
        }
    }
    Rig() {
        d.a0=0x100;d.a1=0x200;d.a2=0x300;d.gif_admit=1;
        d.reset=1;tick();tick();d.reset=0;tick();
    }
    void load() {
        for(unsigned i=0;i<512;++i) {
            d.mem_write=1;d.address=i>>1;d.mem_word_select=i&1;
            d.mem_wdata=uint16_t(i^0xabcd);tick();
        }
        d.mem_write=0;
    }
    void start(bool direction,unsigned length) {
        d.mem_direction=direction;d.mem_length=length-1;d.mem_address=0x1000;
        d.mem_start=1;tick();d.mem_start=0;
    }
    void finish() {while(d.mem_busy||pending||responding||!d.idle)tick();}
};

int main(int argc,char **argv) {
    Verilated::commandArgs(argc,argv);
    Rig r;r.load();r.d.requests=7;r.start(true,512);
    while(r.d.mem_busy)r.tick();
    r.d.gif_admit=0;
    while(r.pending||r.responding||!r.d.idle)r.tick();
    r.d.requests=0;
    assert(r.completed[3]==512);
    assert(r.grants.size()==2048);
    for(unsigned i=0;i<r.grants.size();++i)assert(r.grants[i]==i%4);
    for(unsigned i=0;i<512;++i)assert(r.ram[i]==uint16_t(i^0xabcd));
    for(unsigned i=0;i<3;++i)assert(r.completed[i]>=511&&r.completed[i]<=514);
    std::cout<<"PASS stock512 write with three saturated peers counts=";
    for(auto n:r.completed)std::cout<<n<<",";
    std::cout<<"\n";
    r.d.gif_admit=1;r.d.requests=7;r.start(false,512);
    while(!(r.pending&&r.owner==3))r.tick();
    auto before=r.completed;
    while(r.d.requests) {
        r.tick();
        for(unsigned i=0;i<3;++i)if(r.completed[i]>before[i])r.d.requests&=~(1u<<i);
        r.d.eval();
        if(r.d.requests)assert(!r.d.gif_idle);
    }
    while(!r.d.gif_idle)r.tick();
    for(unsigned i=0;i<3;++i)assert(r.completed[i]==before[i]+1);
    std::cout<<"PASS pending GIF requests retain admission through cancel drain until their ACKs\n";
    while(!(r.pending&&r.owner==3))r.tick();
    before=r.completed;
    r.d.gif_admit=0;r.cancel_mark=true;
    r.stall=true;
    for(unsigned i=0;i<1000;++i) {
        r.tick();assert(r.d.gif_idle&&r.d.mem_busy&&r.d.request&&!r.d.idle);
    }
    r.stall=false;r.due=r.cycles+5;
    while(r.d.mem_busy) {r.tick();assert(r.d.gif_idle);}
    r.finish();
    assert(r.gif_after_cancel==0&&r.completed[3]==1024);
    for(unsigned i=0;i<3;++i)assert(r.completed[i]==before[i]);
    for(unsigned i=0;i<512;++i) {
        r.d.mem_read=1;r.d.address=i>>1;r.d.mem_word_select=i&1;r.tick();
        assert(r.d.mem_rdata==uint16_t(i^0xabcd));
    }
    r.d.mem_read=0;
    std::cout<<"PASS GIF cancel preserves512 MCU reads; GIF idle survives1000 stalled MCU cycles\n";
    r.cancel_mark=false;r.d.gif_admit=1;r.d.requests=7;
    auto initial=r.completed;
    while(r.completed[0]<initial[0]+8||r.completed[1]<initial[1]+8||r.completed[2]<initial[2]+8)r.tick();
    r.d.gif_admit=0;
    while(r.pending||r.responding||!r.d.idle)r.tick();
    r.d.requests=0;
    std::cout<<"PASS GIF restart fairness and held ACK gap cycles="<<r.cycles<<"\n";
    r.d.gif_admit=1;r.d.requests=1;
    while(!r.pending)r.tick();
    assert(r.owner==0);r.d.gif_admit=0;
    while(r.pending) {r.tick();assert(!r.d.gif_idle);}
    r.d.requests=0;
    while(r.responding) {r.tick();if(r.d.ack)assert(!r.d.gif_idle);}
    assert(r.d.gif_idle);
    std::cout<<"PASS in-flight GIF request and held ACK block GIF retirement until drained\n";
}
