/* Experimental original LZW/CI8/GPD1 differential harness with external-memory backpressure. */
#include "Vgif_cached_pipeline.h"
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
    Vgif_cached_pipeline t;
    std::string output_directory;
    bool save_original=false;
    unsigned saved_original=0;
    std::array<uint8_t,76816> memory{};
    std::array<uint32_t,4096> dictionary{};
    bool dictionary_request=false,prefer_dictionary=false;
    uint32_t dictionary_value=0;
    uint64_t dictionary_reads=0,dictionary_writes=0,bus_beats=0,contended=0;
    std::array<uint8_t,76800> reference{},receiver{};
    std::array<bool,1200> dirty{};
    std::vector<uint8_t> packet;
    uint64_t cycles=0, reads=0,writes=0,packets=0,packet_bytes=0;
    bool pending=false,wr=false,stalled=false,last_seen=false,fail_memory=false;
    uint32_t address=0,wait=0,ref_frame=UINT32_MAX;
    uint8_t value=0,stalled_byte=0; bool stalled_last=false;
    bool tick() {
        assert(cycles<5000000000ULL);
        t.clk=0;t.mem_ack=0;t.mem_error=0;t.dict_ack=0;t.dict_error=0;t.eval();
        if(t.reset) pending=false;
        else if(pending) {
            if(dictionary_request) {
                assert(t.dict_valid&&t.dict_key==address&&bool(t.dict_write)==wr);
                assert(!wr||t.dict_wdata==dictionary_value);
            } else {
                assert(t.mem_valid&&t.mem_address==address&&bool(t.mem_write)==wr);
                assert(!wr||t.mem_wdata==value);
            }
            if(wait)wait--;
            else {
                if(dictionary_request) {
                    assert(address<4096);t.dict_ack=1;
                    if(wr){dictionary[address]=dictionary_value;dictionary_writes++;}
                    else {t.dict_rdata=dictionary[address];dictionary_reads++;}
                    bus_beats+=2;
                } else {
                    assert(address<76800);t.mem_ack=1;
                    if(fail_memory){t.mem_error=1;fail_memory=false;}
                    else if(wr){memory[address+8]=value;writes++;}
                    else {t.mem_rdata=memory[address+8];reads++;}
                    bus_beats++;
                }
                pending=false;
            }
        } else if(t.mem_valid||t.dict_valid) {
            if(t.mem_valid&&t.dict_valid)contended++;
            dictionary_request=t.dict_valid&&(!t.mem_valid||prefer_dictionary);
            prefer_dictionary=!dictionary_request;pending=true;
            if(dictionary_request) {
                address=t.dict_key;wr=t.dict_write;dictionary_value=t.dict_wdata;
            } else {address=t.mem_address;wr=t.mem_write;value=t.mem_wdata;}
            wait=unsigned(cycles%3)+(dictionary_request?4:2);
        }
        t.eval();
        if(stalled && !t.cancel && !t.reset) {
            assert(t.out_valid && t.out_byte==stalled_byte && bool(t.out_last)==stalled_last);
        }
        stalled=t.out_valid&&!t.out_ready&&!t.cancel;
        stalled_byte=t.out_byte;stalled_last=t.out_last;
        bool accepted=t.in_valid&&t.in_ready;
        if(t.out_valid&&t.out_ready) {
            assert(!last_seen);packet.push_back(t.out_byte);if(t.out_last)last_seen=true;
        }
        t.clk=1;t.eval();cycles++;
        for(unsigned i=0;i<8;i++)assert(memory[i]==0xa5&&memory[76808+i]==0xa5);
        return accepted;
    }
    void reset() {
        memory.fill(0xa5); t.reset=1; t.cancel=0;t.session_start=0;t.frame_start=0;
        t.emit_packet=0;t.packet_ack=0;t.in_valid=0;t.in_end=0;t.out_ready=0;
        t.bypass_lzw=1;t.generation=1;t.initial_reference=UINT32_MAX;
        t.frame_width=320;t.frame_height=240;t.frame_left=0;t.frame_top=0;
        t.disposal=0;t.interlaced=0;t.local_palette=0;t.transparent=1;
        t.transparent_index=255;t.background_index=255;stalled=false;
        tick();t.reset=0;tick();
    }
    void initialize() {
        t.session_start=1;tick();t.session_start=0;
        uint64_t limit=cycles+1000000;
        while(t.busy){assert(cycles<limit);tick();}
        assert(t.initialized&&!t.error);reference.fill(255);receiver.fill(255);dirty.fill(true);ref_frame=UINT32_MAX;
        for(unsigned i=0;i<76800;i++)assert(memory[i+8]==255);
    }
    void frame(uint32_t id,const std::vector<uint8_t> &data,const std::vector<uint8_t> &expected,unsigned minimum,bool lzw) {
        assert(expected.size()==76800);t.frame_id=id;t.minimum=minimum;t.bypass_lzw=!lzw;
        t.frame_start=1;tick();t.frame_start=0;
        size_t at=0;bool complete=false,decoded=!lzw;uint64_t limit=cycles+5000000;
        while(!complete||!decoded) {
            assert(cycles<limit);t.in_valid=at<data.size()&&cycles%11!=0;
            t.in_end=at==data.size();t.in_byte=at<data.size()?data[at]:0;
            if(tick())at++;
            complete|=t.frame_done;decoded|=t.decode_done;
            assert(!t.error);
        }
        t.in_valid=0;t.in_end=0;assert(at==data.size());
        for(unsigned i=0;i<76800;i++) {
            if(expected[i]!=255&&expected[i]!=reference[i]) {
                reference[i]=expected[i];dirty[(i/320/8)*40+(i%320/8)]=true;
            }
            assert(memory[i+8]==reference[i]);
        }
    }
    void emit(uint32_t id,bool acknowledge=true) {
        packet.clear();last_seen=false;t.emit_packet=1;tick();t.emit_packet=0;
        uint64_t limit=cycles+1000000;
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
        if(!acknowledge)return;
        t.ack_generation=1;t.ack_frame=id;t.packet_ack=1;tick();t.packet_ack=0;
        while(t.busy)tick();
        assert(!t.busy&&!t.error);dirty.fill(false);ref_frame=id;
    }
};
int main(int argc,char **argv) {
    assert(argc==3||argc==4);
    Verilated::commandArgs(argc,argv);Rig r;r.output_directory=argv[2];r.reset();
    r.t.session_start=1;r.tick();r.t.session_start=0;while(!r.pending)r.tick();
    r.t.cancel=1;r.tick();r.t.cancel=0;while(!r.t.cancelled)r.tick();
    assert(!r.t.busy&&!r.t.initialized&&!r.pending);auto writes=r.writes;
    for(unsigned i=0;i<20;i++)r.tick();assert(r.writes==writes);
    r.initialize();
    for(unsigned bad=0;bad<5;bad++) {
        r.t.frame_width=bad==0?319:320;r.t.disposal=bad==1?3:0;
        r.t.local_palette=bad==2;r.t.interlaced=bad==3;r.t.frame_left=bad==4?1:0;
        auto before=r.writes;r.t.frame_start=1;r.tick();r.t.frame_start=0;
        assert(r.t.error&&r.t.frame_done&&!r.t.busy&&r.writes==before);
    }
    r.t.frame_width=320;r.t.disposal=0;r.t.local_palette=0;r.t.interlaced=0;r.t.frame_left=0;
    std::vector<uint8_t> transparent(76800,255);
    r.frame(0,transparent,transparent,8,false);r.emit(0);
    r.frame(1,transparent,transparent,8,false);r.emit(1);assert(r.packet.size()==192);
    puts("PASS cancellation drains memory; five unsupported metadata classes rejected before writes; full initial keyframe and empty update packet; guards and output stalls stable.");
    r.reset();r.initialize();
    std::ifstream f(argv[1],std::ios::binary);assert(f);unsigned total=le32(f);
    unsigned count=argc>3?std::strtoul(argv[3],nullptr,10):total;assert(count<=total);
    if(count==0) {
        r.frame(0,transparent,transparent,8,false);r.emit(0,false);
        r.t.ack_generation=2;r.t.ack_frame=0;r.t.packet_ack=1;r.tick();r.t.packet_ack=0;
        assert(r.t.busy&&r.t.error&&r.t.initialized);
        r.t.ack_generation=1;r.t.ack_frame=99;r.t.packet_ack=1;r.tick();r.t.packet_ack=0;
        assert(r.t.busy&&r.t.error&&r.t.initialized);
        r.t.ack_frame=0;r.t.packet_ack=1;r.tick();r.t.packet_ack=0;
        while(r.t.busy)r.tick();assert(r.t.initialized);
        r.t.bypass_lzw=1;r.t.frame_id=1;r.t.frame_start=1;r.tick();r.t.frame_start=0;
        r.t.in_byte=7;r.t.in_valid=1;while(!r.tick()){}r.t.in_valid=0;r.fail_memory=true;
        while(r.t.busy)r.tick();assert(r.t.error&&!r.t.initialized&&!r.pending);
        auto before=r.writes;for(unsigned i=0;i<20;i++)r.tick();assert(r.writes==before&&!r.t.mem_valid);
        puts("PASS wrong-generation/wrong-frame ACKs preserve pending packet until correct ACK; memory error invalidates session and prevents later writes.");
        return 0;
    }
    r.save_original=true;
    uint64_t max_frame=0,start=r.cycles,start_packets=r.packets,start_bytes=r.packet_bytes;
    uint64_t start_reads=r.reads,start_writes=r.writes;
    auto dr=r.dictionary_reads,dw=r.dictionary_writes,beats=r.bus_beats,contention=r.contended;
    for(unsigned id=0;id<count;id++) {
        unsigned minimum=le32(f),limit=le32(f),n=le32(f),e=le32(f),err=le32(f);
        assert(limit==76800&&e==76800&&!err);
        std::vector<uint8_t> data(n),expected(e);f.read(reinterpret_cast<char*>(data.data()),n);f.read(reinterpret_cast<char*>(expected.data()),e);assert(f);
        uint64_t before=r.cycles;r.frame(id,data,expected,minimum,true);
        if((id%4)==3||id+1==count)r.emit(id);
        if(r.cycles-before>max_frame)max_frame=r.cycles-before;
        if(id%128==0){printf("progress frame=%u cycles=%llu\n",id,(unsigned long long)r.cycles);fflush(stdout);}
    }
    printf("PASS integrated original LZW->external CI8 canvas->GPD1 packet->receiver: frames=%u cycles=%llu max_frame_with_optional_packet=%llu packets=%llu packet_bytes=%llu mem_reads=%llu mem_writes=%llu\n",count,(unsigned long long)(r.cycles-start),(unsigned long long)max_frame,(unsigned long long)(r.packets-start_packets),(unsigned long long)(r.packet_bytes-start_bytes),(unsigned long long)(r.reads-start_reads),(unsigned long long)(r.writes-start_writes));
    printf("Shared serialized service: dictionary_reads=%llu dictionary_writes=%llu modeled_16bit_beats=%llu contended_grants=%llu\n",(unsigned long long)(r.dictionary_reads-dr),(unsigned long long)(r.dictionary_writes-dw),(unsigned long long)(r.bus_beats-beats),(unsigned long long)(r.contended-contention));
    puts("Memory latency/backpressure are synthetic; every four original frames emit one accumulated update. No board timing or OS4 cadence claim; local palettes/interlace/disposal2/3 unsupported.");
}
