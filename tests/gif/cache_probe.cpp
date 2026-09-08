/* Original-GIF prefix lookup cache sensitivity model. This counts actual
   dictionary accesses, not hardware cycles or a synthesized cache design. */
#include <array>
#include <vector>
#include <fstream>
#include <iostream>
#include <cstdint>
#include <stdexcept>
struct Cache {
    unsigned size; bool allocate;
    std::vector<uint16_t> tags;
    uint64_t hits=0,misses=0,writes=0;
    Cache(unsigned n,bool a):size(n),allocate(a),tags(n,65535){}
    void clear(){std::fill(tags.begin(),tags.end(),65535);}
    void read(unsigned key){auto &t=tags[key&(size-1)];if(t==key)hits++;else{misses++;t=key;}}
    void write(unsigned key){writes++;auto &t=tags[key&(size-1)];if(allocate||t==key)t=key;}
};
static uint32_t word(std::ifstream &f) {
    unsigned char b[4];
    if (!f.read((char *)b, sizeof b)) throw std::runtime_error("short fixture word");
    return uint32_t(b[0]) | uint32_t(b[1]) << 8 |
           uint32_t(b[2]) << 16 | uint32_t(b[3]) << 24;
}
int main(int argc,char**argv){
    if(argc!=2)return 2;
    std::ifstream f(argv[1],std::ios::binary);if(!f)return 1;
    unsigned count=word(f),originals=word(f);std::vector<Cache> caches;
    if (!originals || originals > count) throw std::runtime_error("fixture counts");
    for(unsigned n:{64,128,256,512,1024})for(bool a:{false,true})caches.emplace_back(n,a);
    uint64_t walks=0,writes=0;
    for(unsigned frame=0;frame<originals;frame++){
        auto minimum=word(f),limit=word(f),n=word(f),m=word(f),err=word(f);
        (void)limit;(void)err;std::vector<uint8_t> raw(n);f.read((char*)raw.data(),n);f.seekg(m,std::ios::cur);
        if (!f) throw std::runtime_error("short fixture");
        std::array<uint16_t,4096> prefix{};unsigned clear=1u<<minimum,end=clear+1,next=end+1,width=minimum+1;
        uint32_t acc=0;unsigned bits=0,previous=0;bool have=false,done=false;
        for(auto &c:caches)c.clear();
        for(auto byte:raw){
            acc|=uint32_t(byte)<<bits;bits+=8;
            while(bits>=width){
                unsigned code=acc&((1u<<width)-1);acc>>=width;bits-=width;
                if(code==clear){next=end+1;width=minimum+1;have=false;for(auto &c:caches)c.clear();continue;}
                if(code==end){done=true;break;}
                unsigned walk=code==next?previous:code;
                if(code>next || (code==next&&!have))throw std::runtime_error("invalid code");
                unsigned steps=0;
                while(walk>=clear){
                    if(walk>=next||++steps>4096)throw std::runtime_error("invalid chain");
                    for(auto &c:caches)c.read(walk);
                    walks++;walk=prefix[walk];
                }
                if(have&&next<4096){
                    prefix[next]=uint16_t(previous);for(auto &c:caches)c.write(next);writes++;next++;
                    if(next==(1u<<width)&&width<12)width++;
                }
                previous=code;have=true;
            }
            if(done)break;
        }
        if(!done)throw std::runtime_error("missing end");
    }
    std::cout<<"original_frames="<<originals<<" prefix_reads="<<walks<<" dictionary_writes="<<writes<<"\n";
    for(auto &c:caches)std::cout<<"entries="<<c.size<<" write_allocate="<<c.allocate<<" hits="<<c.hits<<" misses="<<c.misses<<" hit_percent="<<(100.0*c.hits/(c.hits+c.misses))<<" external_read_bytes_32bit="<<(c.misses*4)<<"\n";
}
