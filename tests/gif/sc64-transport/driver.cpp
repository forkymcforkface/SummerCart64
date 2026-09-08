/* Experimental original LZW/CI8/GPD1 differential harness with external-memory backpressure. */
#include "Vgif_transport_pipeline.h"
#include "verilated.h"
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <vector>
#include <string>

static uint32_t le32(std::ifstream &f) {
    uint8_t b[4]; f.read(reinterpret_cast<char *>(b), 4); assert(f);
    return uint32_t(b[0]) | uint32_t(b[1])<<8 | uint32_t(b[2])<<16 | uint32_t(b[3])<<24;
}
static uint32_t be32(const std::vector<uint8_t> &v, size_t p) {
    return uint32_t(v[p])<<24 | uint32_t(v[p+1])<<16 | uint32_t(v[p+2])<<8 | v[p+3];
}
struct Rig {
    Vgif_transport_pipeline t;
    std::string output_directory;
    bool save_original=false;
    unsigned saved_original=0;
    std::array<uint8_t,76816> memory{};
    std::vector<uint8_t> dram=std::vector<uint8_t>(64*1024*1024,0);
    std::array<bool,4> active{};
    std::array<uint16_t,4> row{};
    uint64_t read_due=0,refreshes=0,activations=0;
    uint16_t read_value=0;
    bool mode_set=false,traffic=false;
    uint64_t peer_completions[3]={0,0,0},priority_checks=0,reserved_cycles=0;
    uint16_t peer_value[3]={0,0,0};
    bool peer_next_write[3]={true,true,true};
    void peers() {
        auto step=[&](unsigned id,uint8_t &request,uint8_t &write,uint32_t &address,uint16_t &data,uint8_t ack,uint16_t result) {
            if(request&&ack) {
                if(write)peer_value[id]=data;else assert(result==peer_value[id]);
                request=0;peer_next_write[id]=!peer_next_write[id];peer_completions[id]++;
            }
            if(!request&&cycles%8192==0) {
                request=1;write=peer_next_write[id];address=(id+1)*0x1000000;
                data=uint16_t(0xa000+id*256+peer_completions[id]);
            }
        };
        step(0,t.n64_request,t.n64_write,t.n64_address,t.n64_wdata,t.n64_ack,t.n64_rdata);
        step(1,t.usb_request,t.usb_write,t.usb_address,t.usb_wdata,t.usb_ack,t.usb_rdata);
        step(2,t.sd_request,t.sd_write,t.sd_address,t.sd_wdata,t.sd_ack,t.sd_rdata);
        t.pi_active=cycles%8192<24;
        reserved_cycles+=t.pi_active;
    }
    void chip() {
        unsigned cmd=t.chip_command,bank=t.chip_bank,a=t.chip_address;
        if(cmd==3){assert(!active[bank]);active[bank]=true;row[bank]=a;activations++;}
        else if(cmd==2){if(a&1024)active.fill(false);else active[bank]=false;}
        else if(cmd==1){for(bool b:active)assert(!b);refreshes++;}
        else if(cmd==0){assert((a&0x7f)==0x20);mode_set=true;}
        else if(cmd==4||cmd==5) {
            assert(mode_set&&active[bank]&&!(a&1024));
            unsigned address=(bank<<24)|(unsigned(row[bank])<<11)|((a&1023)<<1);
            assert(address+1<dram.size());
            assert(address<16384||(address>=0x10000&&address+1<0x10000+76800)||
                   (address>=0x30000&&address+1<0x38000)||(address>=0x40000&&address+1<0x40000+76992)||
                   address==0x1000000||address==0x2000000||address==0x3000000);
            if(cmd==4) {
                assert(!t.chip_drive);unsigned data=t.chip_dq;
                if(!(t.chip_mask&2))dram[address]=data>>8;
                if(!(t.chip_mask&1))dram[address+1]=data;
                if(address>=0x10000&&address<0x10000+76800) {
                    memory[address-0x10000+8]=dram[address];
                    memory[address-0x10000+9]=dram[address+1];
                }
                if(address>=0x40000&&address<0x40000+76992)output_writes++;
                writes++;
            } else {
                assert(!read_due);read_value=(unsigned(dram[address])<<8)|dram[address+1];
                read_due=cycles+3;reads++;
                if(address>=0x30000&&address<0x38000)source_reads++;
                if(address>=0x40000&&address<0x40000+76992)output_reads++;
            }
        }
    }

    std::array<uint8_t,76800> reference{},receiver{};
    std::array<bool,1200> dirty{};
    std::vector<uint8_t> packet;
    uint64_t cycles=0, reads=0,writes=0,packets=0,packet_bytes=0;
    uint64_t source_bytes=0,readback_cycles=0,source_reads=0,output_reads=0,output_writes=0;
    bool stalled=false,last_seen=false;
    uint32_t ref_frame=UINT32_MAX;
    uint8_t stalled_byte=0; bool stalled_last=false;
    bool tick() {
        assert(cycles<20000000000ULL);
        t.clk=0;t.chip_drive=0;if(traffic)peers();
        if(read_due&&cycles>=read_due){t.chip_drive=1;t.chip_data=read_value;read_due=0;}
        t.eval();
        if(stalled && !t.cancel && !t.reset) {
            assert(t.out_valid && t.out_byte==stalled_byte && bool(t.out_last)==stalled_last);
        }
        stalled=t.out_valid&&!t.stream_output_ready&&!t.cancel;
        stalled_byte=t.out_byte;stalled_last=t.out_last;
        bool accepted=t.in_valid&&t.in_ready;
        if(t.out_valid&&t.stream_output_ready) {
            assert(!last_seen);packet.push_back(t.out_byte);if(t.out_last)last_seen=true;
        }
        bool prior_request=t.arb_request;
        unsigned expected_source=t.n64_request?0:(!t.pi_active&&t.cfg_request)?1:(!t.pi_active&&t.usb_request)?2:(!t.pi_active&&t.sd_request)?3:4;
        t.clk=1;t.eval();
        if(!prior_request&&t.arb_request) {
            assert(expected_source<4);
            if(expected_source==0)assert(t.arb_address==t.n64_address);
            if(expected_source==1)assert(t.arb_address<0x40000+76992);
            if(expected_source==2)assert(t.arb_address==t.usb_address);
            if(expected_source==3)assert(t.arb_address==t.sd_address);
            priority_checks++;
        }
        chip();cycles++;

        return accepted;
    }
    void reset() {
        memory.fill(0xa5);t.chip_drive=0;t.configure=0;t.pi_active=0;
        t.n64_request=0;t.usb_request=0;t.sd_request=0; t.source_length=0;t.verify_start=0;t.verify_ready=0;t.reset=1; t.cancel=0;t.session_start=0;t.frame_start=0;
        t.emit_packet=0;t.packet_ack=0;t.in_valid=0;t.in_end=0;t.out_ready=0;
        t.bypass_lzw=1;t.generation=1;t.initial_reference=UINT32_MAX;
        t.frame_width=320;t.frame_height=240;t.frame_left=0;t.frame_top=0;
        t.disposal=0;t.interlaced=0;t.local_palette=0;t.transparent=1;
        t.transparent_index=255;t.background_index=255;stalled=false;
        tick();t.reset=0;tick();
    }
    void initialize() {
        t.configure=1;tick();t.configure=0;tick();assert(t.configured&&!t.config_error);
        t.session_start=1;tick();t.session_start=0;
        uint64_t limit=cycles+20000000;
        while(t.busy){assert(cycles<limit);tick();}
        assert(t.initialized&&!t.error);reference.fill(255);receiver.fill(255);dirty.fill(true);ref_frame=UINT32_MAX;
        for(unsigned i=0;i<76800;i++)assert(memory[i+8]==255);
    }
    void frame(uint32_t id,const std::vector<uint8_t> &data,const std::vector<uint8_t> &expected,unsigned minimum,bool lzw) {
        assert(expected.size()==76800&&data.size()<=32768);
        assert(!t.source_busy&&!t.output_busy);
        std::copy(data.begin(),data.end(),dram.begin()+0x30000);source_bytes+=data.size();
        t.source_length=unsigned(data.size());t.frame_id=id;t.minimum=minimum;t.bypass_lzw=0;
        t.frame_start=1;tick();t.frame_start=0;
        bool complete=false,decoded=false;uint64_t limit=cycles+20000000;
        while(!complete||!decoded) {
            assert(cycles<limit);tick();complete|=t.frame_done;decoded|=t.decode_done;assert(!t.error);
        }
        while(t.source_busy){assert(cycles<limit);tick();}
        assert(t.source_consumed==data.size());
        for(unsigned i=0;i<76800;i++) {
            if(expected[i]!=255&&expected[i]!=reference[i]) {
                reference[i]=expected[i];dirty[(i/320/8)*40+(i%320/8)]=true;
            }
            assert(memory[i+8]==reference[i]);
        }
    }
    void emit(uint32_t id,bool acknowledge=true) {
        packet.clear();last_seen=false;t.emit_packet=1;tick();t.emit_packet=0;
        uint64_t limit=cycles+20000000;
        while(!t.packet_done){assert(cycles<limit);t.out_ready=cycles%7!=0;tick();assert(!t.error);}
        t.out_ready=0;assert(last_seen&&packet.size()>=192&&packet.size()%16==0);
        assert(be32(packet,0)==0x47504431&&be32(packet,4)==1&&be32(packet,8)==id);
        assert(be32(packet,12)==ref_frame&&be32(packet,16)==0x014000f0&&be32(packet,20)==1);
        unsigned count=0;for(bool d:dirty)count+=d;
        assert(be32(packet,24)==count&&be32(packet,28)==count*64&&packet.size()==192+count*64);
        for(unsigned i=182;i<192;i++)assert(packet[i]==0);
        size_t pos=192;
        for(unsigned tile=0;tile<1200;tile++) {
            assert(bool(packet[32+tile/8]&(1u<<(tile%8)))==dirty[tile]);
            if(dirty[tile])for(unsigned y=0;y<8;y++)for(unsigned x=0;x<8;x++) {
                unsigned p=(tile/40*8+y)*320+tile%40*8+x;
                assert(packet[pos]==reference[p]);receiver[p]=packet[pos++];
            }
        }
        assert(receiver==reference);packets++;packet_bytes+=packet.size();
        if(save_original&&saved_original++<16) {
            char name[64];std::snprintf(name,sizeof name,"/original-%04u.gpd",id);
            std::ofstream f(output_directory+name,std::ios::binary);
            f.write(reinterpret_cast<char*>(packet.data()),packet.size());assert(f);
        }
        while(t.output_busy){assert(cycles<limit);tick();}
        assert(t.output_length==packet.size());
        uint64_t verify_begin=cycles;t.verify_start=1;tick();t.verify_start=0;
        size_t readback=0;
        while(readback<packet.size()) {
            assert(cycles<limit);t.verify_ready=cycles%7!=0;t.clk=0;t.eval();
            if(t.verify_ready&&t.verify_valid)assert(t.verify_byte==packet[readback++]);
            tick();
        }
        t.verify_ready=0;while(t.source_busy){assert(cycles<limit);tick();}
        assert(t.source_consumed==packet.size());readback_cycles+=cycles-verify_begin;
        if(!acknowledge)return;
        t.ack_generation=1;t.ack_frame=id;t.packet_ack=1;tick();t.packet_ack=0;
        while(t.busy)tick();
        assert(!t.busy&&!t.error);dirty.fill(false);ref_frame=id;
    }
};
int main(int argc,char **argv) {
    assert(argc==3||argc==4);
    Verilated::commandArgs(argc,argv);Rig r;r.output_directory=argv[2];r.reset();r.initialize();r.traffic=true;
    std::ifstream f(argv[1],std::ios::binary);assert(f);unsigned total=le32(f);
    unsigned count=argc>3?std::strtoul(argv[3],nullptr,10):total;assert(count<=total);
    r.save_original=true;
    uint64_t max_frame=0,start=r.cycles,start_packets=r.packets,start_bytes=r.packet_bytes;
    uint64_t start_reads=r.reads,start_writes=r.writes;
    std::ofstream ledger(r.output_directory+"/frame-cycles.csv");assert(ledger);
    ledger<<"frame,cycles,readback_cycles,packet_bytes,source_bytes,sdram_reads,sdram_writes\n";
    for(unsigned id=0;id<count;id++) {
        unsigned minimum=le32(f),limit=le32(f),n=le32(f),e=le32(f),err=le32(f);
        assert(limit==76800&&e==76800&&!err);
        std::vector<uint8_t> data(n),expected(e);f.read(reinterpret_cast<char*>(data.data()),n);f.read(reinterpret_cast<char*>(expected.data()),e);assert(f);
        uint64_t before=r.cycles,prior_readback=r.readback_cycles,prior_bytes=r.packet_bytes,prior_reads=r.reads,prior_writes=r.writes;r.frame(id,data,expected,minimum,true);
        if((id%4)==3||id+1==count)r.emit(id);
        ledger<<id<<","<<r.cycles-before<<","<<r.readback_cycles-prior_readback<<","<<r.packet_bytes-prior_bytes<<","<<data.size()<<","<<r.reads-prior_reads<<","<<r.writes-prior_writes<<"\n";assert(ledger);
        if(r.cycles-before>max_frame)max_frame=r.cycles-before;
        if(id%128==0){printf("progress frame=%u cycles=%llu\n",id,(unsigned long long)r.cycles);fflush(stdout);}
    }
    printf("PASS integrated original LZW->external CI8 canvas->GPD1 packet->receiver: frames=%u cycles=%llu max_frame_with_optional_packet=%llu packets=%llu packet_bytes=%llu mem_reads=%llu mem_writes=%llu\n",count,(unsigned long long)(r.cycles-start),(unsigned long long)max_frame,(unsigned long long)(r.packets-start_packets),(unsigned long long)(r.packet_bytes-start_bytes),(unsigned long long)(r.reads-start_reads),(unsigned long long)(r.writes-start_writes));
    printf("Transport: source_bytes=%llu source_word_reads=%llu output_word_writes=%llu readback_word_reads=%llu readback_cycles=%llu\n",(unsigned long long)r.source_bytes,(unsigned long long)r.source_reads,(unsigned long long)r.output_writes,(unsigned long long)r.output_reads,(unsigned long long)r.readback_cycles);
    printf("Concurrent requests: N64=%llu USB=%llu SD=%llu checked_grants=%llu reserved_cycles=%llu\n",(unsigned long long)r.peer_completions[0],(unsigned long long)r.peer_completions[1],(unsigned long long)r.peer_completions[2],(unsigned long long)r.priority_checks,(unsigned long long)r.reserved_cycles);
    printf("Actual SDRAM commands: refreshes=%llu activations=%llu\n",(unsigned long long)r.refreshes,(unsigned long long)r.activations);
    puts("Memory latency/backpressure are synthetic; every four original frames emit one accumulated update. No board timing or OS4 cadence claim; local palettes/interlace/disposal2/3 unsupported.");
}
