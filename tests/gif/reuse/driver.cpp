/* Runtime comparison/replay regression with delayed single-beat scratch memory.
 * Expected equality is independently checked from original input bytes. */
#include "Vreuse_test.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
static void check(bool ok,const char*s){if(!ok)throw std::runtime_error(s);}
static uint32_t word(std::ifstream&f){uint8_t b[4];f.read(reinterpret_cast<char*>(b),4);check(bool(f),"truncated fixture");return uint32_t(b[0])|uint32_t(b[1])<<8|uint32_t(b[2])<<16|uint32_t(b[3])<<24;}
struct Rig {
 Vreuse_test d;std::vector<uint8_t>ram=std::vector<uint8_t>(51512,0xa5);
 uint64_t cycles=0,reads=0,writes=0;bool pending=false;unsigned addr=0,data=0,mask=0,wr=0,delay=0,hold=0;
 void tick(){check(++cycles<2000000000ULL,"watchdog");d.clk=0;d.eval();d.ack=0;
  if(hold){d.ack=1;--hold;}
  else if(pending){check(d.request&&d.address==addr&&d.wdata==data&&d.wmask==mask&&d.write==wr,"unstable beat");
   if(delay)--delay;else{check(addr>=8&&addr+1<51504&&!(addr&1),"scratch bounds");
    if(wr){if(mask&2)ram[addr]=data>>8;if(mask&1)ram[addr+1]=data;writes++;}else reads++;
    d.rdata=(ram[addr]<<8)|ram[addr+1];d.ack=1;pending=false;hold=cycles%3;
   }
  }else if(d.request){pending=true;addr=d.address;data=d.wdata;mask=d.wmask;wr=d.write;delay=cycles%4;}
  d.eval();d.clk=1;d.eval();
 }
 Rig(){d.reset=1;tick();d.reset=0;configure();}
 void idle(){while(d.busy||hold||pending)tick();}
 void configure(){idle();d.arena_begin=8;d.arena_end=51504;d.buffer_base=8;d.configure=1;tick();d.configure=0;check(d.configured&&!d.error,"configure");}
 void begin(unsigned n,const std::array<uint32_t,6>&meta={},unsigned epoch=1,unsigned disp=0){idle();d.length=n;d.epoch=epoch;d.disposal=disp;for(unsigned i=0;i<6;i++)d.metadata[i]=meta[i];d.start=1;tick();d.start=0;check(!d.error,"begin");}
 void feed(const std::vector<uint8_t>&v){size_t p=0;while(p<v.size()){d.in_valid=cycles%7!=0;d.in_byte=v[p];d.clk=0;d.eval();bool accepted=d.in_valid&&d.in_ready;tick();if(accepted)p++;}d.in_valid=0;while(!d.result_valid)tick();}
 bool finish(const std::vector<uint8_t>&v,bool success=true){bool hit=d.result_hit;if(!hit){d.replay_start=1;tick();d.replay_start=0;size_t p=0;while(p<v.size()){d.out_ready=cycles%5!=0;d.clk=0;d.eval();if(d.out_valid){check(d.out_byte==v[p],"replay bytes");check(bool(d.out_last)==(p+1==v.size()),"replay last");if(d.out_ready)p++;}tick();}d.out_ready=0;}
  d.commit_success=success;d.commit_valid=1;tick();d.commit_valid=0;idle();return hit;}
 bool frame(const std::vector<uint8_t>&v,const std::array<uint32_t,6>&m={},unsigned epoch=1,unsigned disp=0,bool success=true){begin(v.size(),m,epoch,disp);feed(v);return finish(v,success);}
 void cancel(){d.cancel=1;tick();d.cancel=0;d.in_valid=0;while(!d.cancelled)tick();idle();check(!d.configured,"cancel config");auto n=writes+reads;for(unsigned i=0;i<10;i++)tick();check(n==writes+reads,"late cancel beat");configure();}
};
int main(int argc,char**argv){try{check(argc==2||argc==3,"usage payloads.bin [focused]");{ Rig r;
 std::vector<uint8_t>v(25747);for(unsigned i=0;i<v.size();i++)v[i]=(i*37)^0x5a;
 check(!r.frame(v),"initial hit");check(r.frame(v),"identical miss");v.back()^=1;check(!r.frame(v),"last byte mismatch hit");
 v.pop_back();check(!r.frame(v),"size mismatch hit");
 std::array<uint32_t,6>m{};for(unsigned bit=0;bit<192;++bit){m[bit/32]^=1u<<(bit%32);check(!r.frame(std::vector<uint8_t>{1,2,3},m),"metadata mismatch hit");}
 std::vector<uint8_t>small{1,2,3};check(!r.frame(small,{},2),"epoch mismatch hit");check(!r.frame(small,{},2,2),"unsupported disposal hit");check(!r.frame(small,{},2,2),"unsupported repeat hit");
 check(!r.frame(small,{},3,0,false),"failed frame hit");check(!r.frame(small,{},3),"failed commit retained");check(r.frame(small,{},3),"committed repeat miss");
 for(unsigned offset=0;offset<80;++offset){r.begin(3);size_t p=0;for(unsigned i=0;i<offset;i++){r.d.in_valid=p<3;r.d.in_byte=p<3?small[p]:0;r.d.clk=0;r.d.eval();bool a=r.d.in_valid&&r.d.in_ready;r.tick();if(a)p++;}r.cancel();check(!r.frame(small),"cancel retained identity");}
 for(unsigned n:{0u,25748u,65535u}){r.idle();r.d.length=n;r.d.start=1;r.tick();r.d.start=0;check(r.d.error&&!r.d.busy,"invalid length accepted");}
 for(unsigned kind=0;kind<5;++kind){r.configure();
  if(kind==0)r.d.buffer_base=9;
  if(kind==1)r.d.arena_end=51503;
  if(kind==2)r.d.buffer_base=0x7fffffe;
  if(kind==3)r.d.arena_end=0x4000001;
  if(kind==4)r.d.arena_begin=r.d.arena_end;
  r.d.configure=1;r.tick();r.d.configure=0;check(r.d.error&&!r.d.configured,"invalid arena accepted");
 }
 for(unsigned phase=0;phase<5;++phase){r.configure();std::vector<uint8_t>next{0xe1,0x42,0x93};
  if(phase==4)check(!r.frame(next),"fresh hit");
  r.begin(next.size());r.feed(next);check(bool(r.d.result_hit)==(phase==4),"phase eligibility");
  if(phase<4){r.d.replay_start=1;r.tick();r.d.replay_start=0;
   if(phase==1){r.tick();check(r.d.request,"replay read not issued");}
   if(phase==2){while(!r.d.out_valid)r.tick();for(unsigned i=0;i<10;i++){check(r.d.out_byte==next[0],"stalled replay byte");r.tick();}}
   if(phase==3){size_t at=0;r.d.out_ready=1;while(at<next.size()){r.d.clk=0;r.d.eval();if(r.d.out_valid){check(r.d.out_byte==next[at],"commit phase replay");at++;}r.tick();}r.d.out_ready=0;}
  }
  r.cancel();check(!r.frame(std::vector<uint8_t>{0x1e,0xbd,0x6c}),"cancel reused opposite payload");
 }
 if(argc==3){std::cout<<"PASS focused metadata_bits=192 cancellation_offsets=80 cancellation_phases=5 invalid_arenas=5\n";return 0;}
 } Rig r;std::ifstream f(argv[1],std::ios::binary);check(bool(f),"open fixtures");unsigned count=word(f),hits=0;std::vector<uint8_t>prior;std::array<uint32_t,6>pm{};unsigned pe=0,pd=7;bool valid=false;uint64_t start=r.cycles,sr=r.reads,sw=r.writes;
 for(unsigned i=0;i<count;++i){unsigned n=word(f),epoch=word(f),disp=word(f);check(n>0&&n<=25747,"fixture length");std::array<uint32_t,6>meta;for(auto&x:meta)x=word(f);std::vector<uint8_t>raw(n);f.read(reinterpret_cast<char*>(raw.data()),n);check(bool(f),"fixture payload");bool expected=valid&&disp<=1&&pd<=1&&pe==epoch&&meta==pm&&raw==prior;bool hit=r.frame(raw,meta,epoch,disp);check(hit==expected,"original reuse disagreement");hits+=hit;prior=raw;pm=meta;pe=epoch;pd=disp;valid=true;}
 for(unsigned i=0;i<8;i++)check(r.ram[i]==0xa5&&r.ram[51504+i]==0xa5,"guards");
 std::cout<<"PASS original_frames="<<count<<" exact_hits="<<hits<<" cycles="<<r.cycles-start<<" reads="<<r.reads-sr<<" writes="<<r.writes-sw<<" metadata_bits=192 cancellation_offsets=80\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
