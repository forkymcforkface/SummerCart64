/* Finite arbitration observations with held requests and delayed responses.
   Counts and longest observed pending intervals are measurements, not liveness
   proofs. Stock continuous CFG is the lower-priority starvation control. */
#include "Vfairness.h"
#include "verilated.h"
#include <array>
#include <cstdint>
#include <cstdio>
#include <stdexcept>

int main(int argc,char **argv) {
    Verilated::commandArgs(argc,argv);
    for(unsigned delay: {0u,3u,17u}) for(unsigned windows: {0u,1u})
    for(unsigned mode=0;mode<3;mode++) for(unsigned load=0;load<3;load++) {
        Vfairness d;
        std::array<uint64_t,7> grants{},wait{},maximum{};
        bool pending=false,usb=true,sd=true,n64=false;
        unsigned address=0,left=0,cooldown=0;
        uint64_t completed=0,cycles=0,pi_decisions=0,peer_gap_decisions=0;
        d.mux_enable=mode==1;d.cfg_enable=mode!=2;d.requests=15;
        d.reset=1;d.clk=0;d.eval();d.clk=1;d.eval();d.reset=0;
        for(;cycles<100000&&completed<3000;cycles++) {
            bool pi=windows&&(cycles%257<32);
            if(pi)n64=true;
            if(load==0){usb=true;sd=true;}
            if(load==1&&!usb&&!sd){
                if(cooldown)cooldown--;
                else {usb=true;sd=true;}
            }
            if(load==2){usb=false;sd=true;}
            d.clk=0;d.pi_active=pi;
            d.requests=15|(unsigned(usb)<<4)|(unsigned(sd)<<5)|(unsigned(n64)<<6);
            d.memory_ack=0;d.eval();
            if(d.memory_request) {
                if(!pending){pending=true;address=d.memory_address;left=delay;}
                if(address!=d.memory_address)throw std::runtime_error("request address changed");
                if(left)left--;
                else {d.memory_ack=1;d.memory_rdata=uint16_t(address^0x5a5a);}
            } else if(pending)throw std::runtime_error("request dropped before ACK");
            d.eval();
            unsigned acks=d.acknowledgements;
            if(d.memory_ack) {
                if(!acks||(acks&(acks-1)))throw std::runtime_error("ACK not exactly one owner");
                unsigned owner=(address-0x100)/4;
                if(address<0x100||owner>=7||address!=0x100+4*owner||acks!=(1u<<owner))
                    throw std::runtime_error("ACK wrong owner");
                uint16_t data=uint16_t(d.readback[owner/2]>>(16*(owner%2)));
                if(data!=uint16_t(address^0x5a5a))throw std::runtime_error("readback mismatch");
                completed++;pending=false;
            } else if(acks)throw std::runtime_error("unsolicited ACK");
            for(unsigned i=0;i<7;i++) {
                if(d.requests&(1u<<i))wait[i]++;
                if(wait[i]>maximum[i])maximum[i]=wait[i];
                if(acks&(1u<<i)){grants[i]++;wait[i]=0;}
                if(!(d.requests&(1u<<i)))wait[i]=0;
            }
            bool idle=!d.memory_request;
            bool cfg_before=d.cfg_request;
            d.clk=1;d.eval();
            if(idle&&d.memory_request&&pi) {
                pi_decisions++;
                if(d.memory_address!=0x118)throw std::runtime_error("PI reservation bypassed");
            }
            if(idle&&d.memory_request&&(d.memory_address==0x110||d.memory_address==0x114)) {
                if(cfg_before)throw std::runtime_error("peer admitted without CFG gap");
                peer_gap_decisions++;
            }
            if(acks&16){usb=false;cooldown=19;}
            if(acks&32){sd=false;cooldown=19;}
            if(acks&64)n64=false;
        }
        if(completed!=3000)throw std::runtime_error("incomplete finite observations");
        if(mode==0&&(grants[4]||grants[5]))throw std::runtime_error("continuous CFG control did not starve peers");
        if(mode!=0&&load==0&&(!grants[4]||grants[5]))throw std::runtime_error("stock USB priority mismatch");
        if(mode!=0&&load==1&&(!grants[4]||!grants[5]))throw std::runtime_error("paired peers did not progress");
        if(mode!=0&&load==2&&!grants[5])throw std::runtime_error("SD-only did not progress");
        if(mode==1)for(unsigned i=0;i<4;i++) {
            if(!grants[i])throw std::runtime_error("mux owner did not progress");
            for(unsigned j=0;j<4;j++)if(grants[i]>grants[j]+1)throw std::runtime_error("mux rotation imbalance");
        }
        if(peer_gap_decisions!=grants[4]+grants[5])throw std::runtime_error("peer gap count mismatch");
        if(windows&&!pi_decisions)throw std::runtime_error("PI windows not exercised");
        printf("{\"mode\":%u,\"load\":%u,\"delay\":%u,\"windows\":%u,\"cycles\":%llu,\"completed\":%llu,\"grants\":[",
               mode,load,delay,windows,(unsigned long long)cycles,(unsigned long long)completed);
        for(unsigned i=0;i<7;i++)printf("%s%llu",i?",":"",(unsigned long long)grants[i]);
        printf("],\"max_pending_cycles\":[");
        for(unsigned i=0;i<7;i++)printf("%s%llu",i?",":"",(unsigned long long)maximum[i]);
        printf("],\"pi_decisions\":%llu,\"peer_gap_decisions\":%llu}\n",
               (unsigned long long)pi_decisions,(unsigned long long)peer_gap_decisions);
    }
}
