/* Adversarial mem_bus responder: stable requests, held acknowledgements,
 * exact byte lanes, bounded arenas and cancellation at both dictionary beats. */
#include "Vbus_test.h"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>
static void require(bool ok, const char *s) { if (!ok) throw std::runtime_error(s); }
struct Rig {
 Vbus_test d;
 std::vector<uint8_t> ram=std::vector<uint8_t>(0x30000,0xa5);
 uint64_t ticks=0, beats=0;
 bool pending=false;
 unsigned address=0,data=0,mask=0,write=0,delay=0,hold=0;
 void tick() {
  require(++ticks<2000000,"watchdog");
  d.clk=0; d.eval(); d.ack=0;
  if(hold) { d.ack=1; --hold; }
  else if(pending) {
   require(d.request && d.address==address && d.wdata==data && d.wmask==mask && d.write==write,"unstable pending beat");
   if(!delay--) {
    require(!(address&1) && address+1<ram.size(),"bus bounds/alignment");
    if(write) { if(mask&2) ram[address]=data>>8; if(mask&1) ram[address+1]=data; }
    d.rdata=(ram[address]<<8)|ram[address+1]; d.ack=1;
    pending=false; hold=3; ++beats;
   }
  } else if(d.request) {
   pending=true; address=d.address; data=d.wdata; mask=d.wmask; write=d.write;
   delay=unsigned(ticks%13)+1;
  }
  d.eval(); d.clk=1; d.eval();
 }
 Rig() { d.reset=1; tick(); d.reset=0; }
 void idle() { for(unsigned n=0;n<1000 && (d.busy||hold||pending);++n) tick(); require(!d.busy&&!pending&&!hold,"idle timeout"); }
 void config(bool good=true) {
  idle(); d.configure=1; tick(); d.configure=0;
  require(bool(d.configured)==good && bool(d.config_error)!=good,"configuration validation");
 }
 void valid_config() { d.arena_begin=0x10000; d.arena_end=0x26c00; d.dictionary_base=0x10000; d.canvas_base=0x14000; config(); }
 uint32_t op(bool dict,bool wr,unsigned key,unsigned val=0,bool error=false) {
  idle();
  if(dict) { d.dict_valid=1;d.dict_write=wr;d.dict_key=key;d.dict_wdata=val; }
  else {d.canvas_valid=1;d.canvas_write=wr;d.canvas_address=key;d.canvas_wdata=val;}
  for(unsigned n=0;n<1000;++n) {tick(); if(dict?d.dict_ack:d.canvas_ack) {
   require(bool(dict?d.dict_error:d.canvas_error)==error,"operation error status");
   unsigned result=dict?d.dict_rdata:d.canvas_rdata;d.dict_valid=0;d.canvas_valid=0;idle();return result;
  }} throw std::runtime_error("operation timeout");
 }
};
int main() { try {
 Rig r; r.valid_config();
 for(unsigned i=0;i<4096;++i) r.op(true,true,i,(i*197u)^0xabcdeu);
 for(unsigned i=0;i<4096;++i) require(r.op(true,false,i)==(((i*197u)^0xabcdeu)&0xfffff),"dictionary roundtrip");
 for(unsigned i: {0u,1u,2u,3u,76798u,76799u}) { r.op(false,true,i,i^0x5a);require(r.op(false,false,i)==((i^0x5a)&255),"canvas lane"); }
 require(r.ram[0x14004]==0xa5 && r.ram[0x26c00]==0xa5 && r.ram[0xffff]==0xa5,"guards");
 auto b=r.beats;r.op(false,false,76800,0,true);require(r.beats==b,"invalid canvas issued beat");
 r.d.canvas_base=0x10000;r.config(false);
 r.valid_config();r.d.dictionary_base=0x10002;r.config(false);
 r.valid_config();r.d.canvas_base=0x14001;r.config(false);
 r.valid_config();r.d.arena_end=0x26bff;r.config(false);
 r.valid_config();r.d.dictionary_base=0x7fffffc;r.config(false);
 r.valid_config();r.d.arena_end=0x4000001;r.config(false);
 r.valid_config();r.d.arena_begin=0x26c00;r.config(false);
 b=r.beats;r.op(true,false,0,0,true);require(r.beats==b,"unconfigured bus access");
 r.valid_config();
 r.d.dict_valid=1;r.d.dict_write=0;r.d.dict_key=0;
 r.d.canvas_valid=1;r.d.canvas_write=0;r.d.canvas_address=0;
 unsigned dc=0,cc=0;
 for(unsigned i=0;i<10000 && (dc<10 || cc<10);++i) {
  r.tick();dc+=r.d.dict_ack;cc+=r.d.canvas_ack;
  require(dc<=cc+1 && cc<=dc+1,"round robin starvation");
 }
 require(dc>=10 && cc>=10,"round robin timeout");
 r.d.dict_valid=0;r.d.canvas_valid=0;r.idle();
 r.d.dict_valid=1;r.d.dict_write=1;r.d.dict_key=1;r.d.dict_wdata=0x54321;
 while(!r.pending)r.tick();
 r.d.configure=1;r.d.dictionary_base=0x20000;r.tick();r.d.configure=0;
 require(r.d.config_error,"busy reconfiguration accepted");
 while(!r.d.dict_ack)r.tick();r.d.dict_valid=0;r.idle();
 require(r.op(true,false,1)==0x54321,"busy reconfiguration changed active base");
 for(unsigned phase=0;phase<3;++phase) {
  r.valid_config();b=r.beats;r.d.dict_valid=1;r.d.dict_write=1;r.d.dict_key=9;r.d.dict_wdata=0x12345;
  if(phase==0) {while(!r.pending)r.tick();}
  if(phase==1) {while(r.beats==b)r.tick();}
  if(phase==2) {while(r.beats<b+1 || !r.pending)r.tick();}
  r.d.cancel=1;r.tick();r.d.cancel=0;
  while(!r.d.cancelled)r.tick();
  require(r.d.dict_ack && r.d.dict_error,"phase cancel response");
  r.d.dict_valid=0;r.idle();
  require(r.beats==b+(phase==2?2:1),"cancel issued extra dictionary beat");
 }
 for(unsigned offset=0;offset<65;++offset) {
  r.valid_config();r.d.dict_valid=1;r.d.dict_write=1;r.d.dict_key=7;r.d.dict_wdata=0xabcde;
  r.d.canvas_valid=1;r.d.canvas_write=1;r.d.canvas_address=5;r.d.canvas_wdata=0x23;
  bool da=false,ca=false;
  for(unsigned i=0;i<offset;++i) {r.tick();if(r.d.dict_ack){r.d.dict_valid=0;da=true;}if(r.d.canvas_ack){r.d.canvas_valid=0;ca=true;}}
  r.d.cancel=1;r.tick();r.d.cancel=0;
  bool done=false;
  for(unsigned i=0;i<1000;++i) {
   if(r.d.dict_ack){require(r.d.dict_error,"cancel dictionary error ACK");r.d.dict_valid=0;da=true;}
   if(r.d.canvas_ack){require(r.d.canvas_error,"cancel canvas error ACK");r.d.canvas_valid=0;ca=true;}
   if(r.d.cancelled){done=true;break;} r.tick();
  }
  require(done && da && ca && !r.d.configured && !r.d.request,"cancel drain/status");
  b=r.beats;r.idle();for(unsigned i=0;i<20;++i)r.tick();require(r.beats==b,"post-cancel beat");
 }
 r.valid_config();require(r.op(true,false,7)<=0xfffff,"restart");
 std::cout<<"PASS dictionary=4096 canvas_lanes=6 invalid_configs=7 cancel_offsets=65 cycles="<<r.ticks<<" beats="<<r.beats<<"\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;} }
