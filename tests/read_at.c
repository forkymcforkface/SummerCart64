/* Actual cfg cases, address translation, diagnostics and SD read implementation. */
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include "sd.h"
#include "read-at-types.inc"
#define READ_AT_MAX_BLOCKS (DATA_BUFFER_SIZE / SD_SECTOR_SIZE)
_Static_assert(DATA_BUFFER_SIZE == sizeof(((sc64_buffers_t *)0)->BUFFER), "controller/N64 BRAM capacity mismatch");
_Static_assert(READ_AT_MAX_BLOCKS == 16, "READ_AT capability block limit changed");
static struct { uint32_t data[2],sd_card_sector; } p;
static struct {bool card_initialized,byte_swap,card_type_block;} sdstate;
static unsigned lock_fail,fault,lock_calls,on,off,starts,aborts,cmd18,cmd12,adc_calls;
static uint32_t reply0,reply1,status,read_address,read_count;
static unsigned char bram[DATA_BUFFER_SIZE];
static void cfg_cmd_reply_success(void){reply0=p.data[0];reply1=p.data[1];status=0;}
static void cfg_cmd_reply_error(unsigned type,uint32_t error){reply0=type<<24|error;reply1=0;status=1;}
sd_error_t sd_get_lock(sd_lock_t lock){assert(lock==SD_LOCK_N64);return ++lock_calls==lock_fail?SD_ERROR_LOCKED:SD_OK;}
static void led_activity_on(void){on++;}
static void led_activity_off(void){off++;}
static void hw_adc_read_voltage_temperature(uint16_t *v,int16_t *t){adc_calls++;*v=3300;*t=25;}
static void sd_start_read(uint32_t address,uint32_t count){assert(address == DATA_BUFFER_ADDRESS && count >= 1 && count <= READ_AT_MAX_BLOCKS);read_address=address;read_count=count;starts++;}
static void sd_abort(void){aborts++;}
static int sd_cmd(unsigned cmd,uint32_t sector,unsigned rsp,void *unused){
 (void)unused;
 if(cmd==12){assert(rsp==RSP_R1b);cmd12++;return 0;}
 assert(cmd==18 && rsp==RSP_R1);cmd18++;
 if(fault==1)return 1;
 for(unsigned i=0;i<read_count*SD_SECTOR_SIZE;i++)bram[i]=(unsigned char)(sector+(sdstate.byte_swap?(i^1):i));
 return 0;
}
static dat_status_t sd_sync(unsigned timeout){assert(timeout==TIMEOUT_DATA_MS);return fault==2?DAT_ERROR_IO:fault==3?DAT_ERROR_TIMEOUT:DAT_OK;}
#include "read-at-sd.inc"
#include PHOS_READ_AT_OWNER
struct result {uint32_t cursor,r0,r1,status;unsigned locks,on,off,starts,aborts,cmd18,cmd12;unsigned char data[DATA_BUFFER_SIZE];};
static void reset(unsigned lf,unsigned fail,unsigned init,unsigned swap,unsigned block){
 memset(&p,0,sizeof(p));p.sd_card_sector=0xCAFE0123;memset(bram,0xA5,sizeof(bram));
 sdstate.card_initialized=init;sdstate.byte_swap=swap;sdstate.card_type_block=block;
 lock_fail=lf;fault=fail;lock_calls=on=off=starts=aborts=cmd18=cmd12=adc_calls=0;reply0=reply1=status=read_address=read_count=0;
}
static struct result snapshot(void){struct result r={0};r.cursor=p.sd_card_sector;r.r0=reply0;r.r1=reply1;r.status=status;r.locks=lock_calls;r.on=on;r.off=off;r.starts=starts;r.aborts=aborts;r.cmd18=cmd18;r.cmd12=cmd12;memcpy(r.data,bram,sizeof(bram));return r;}
int main(void){
 assert(CMD_ID_SD_SECTOR_SET=='I' && CMD_ID_SD_READ=='s' && CMD_ID_SD_READ_AT=='R' && CMD_ID_DIAGNOSTIC_GET=='%');
 assert(DIAGNOSTIC_ID_READ_AT==0x50485241);
 const uint32_t lbas[]={0,1234,0xFFFFFFF0,0xFFFFFFFF};
 const uint32_t counts[]={0,1,2,15,16,17,31,256,0x10000,0x800000,0xFFFFFFFF};unsigned cases=0;
 for(unsigned l=0;l<4;l++)for(unsigned n=0;n<11;n++)for(unsigned lf=0;lf<3;lf++)
 for(unsigned init=0;init<2;init++)for(unsigned swap=0;swap<2;swap++)for(unsigned block=0;block<2;block++)for(unsigned fail=0;fail<4;fail++){
  uint32_t count=counts[n],lba=lbas[l];
  reset(lf,fail,init,swap,block);p.data[0]=lba;legacy_command('I');
  if(!status){p.data[0]=SC64_BUFFERS_BASE;p.data[1]=count;legacy_command('s');}
  struct result a=snapshot();
  reset(lf,fail,init,swap,block);p.data[0]=lba;p.data[1]=count;read_at_command('R');
  struct result b=snapshot();assert(!memcmp(&a,&b,sizeof(a)));assert(on==off);
  if(lf==1){assert(p.sd_card_sector==0xCAFE0123 && reply0==(2u<<24|SD_ERROR_LOCKED));}
  else if(count==0 || (count>READ_AT_MAX_BLOCKS && count<0x800000)){assert(p.sd_card_sector==lba && reply0==(2u<<24|SD_ERROR_INVALID_ADDRESS) && !starts);}
  else if(count>=0x800000){assert(p.sd_card_sector==lba && reply0==(2u<<24|SD_ERROR_INVALID_ARGUMENT) && !starts);}
  else if(status)assert(p.sd_card_sector==lba);
  else assert(p.sd_card_sector==lba+count);
  cases++;
 }
 const uint32_t overflow_counts[]={0x700100,0x780000,0x7FFFFE,0x7FFFFF};
 for(unsigned i=0;i<4;i++)for(unsigned lf=0;lf<3;lf++)for(unsigned init=0;init<2;init++){
  reset(lf,0,init,0,1);p.data[0]=1234;p.data[1]=overflow_counts[i];read_at_command('R');
  assert(status && !starts && !on && !off);
  assert(reply0==(2u<<24|(lf==1?SD_ERROR_LOCKED:SD_ERROR_INVALID_ADDRESS)));
  assert(p.sd_card_sector==(lf==1?0xCAFE0123:1234));
 }
 reset(0,0,1,0,1);p.data[0]=0xFFFFFFFF;p.data[1]=0;read_at_command('%');assert(status && reply0==0x01000004 && !lock_calls && !starts && !adc_calls);
 reset(0,0,1,0,1);p.data[0]=DIAGNOSTIC_ID_READ_AT;p.data[1]=0;read_at_command('%');assert(!status && reply0==0x52415431 && reply1==0x52010010 && !lock_calls && !starts && !adc_calls && p.sd_card_sector==0xCAFE0123);
 reset(0,0,1,0,1);p.data[0]=0;read_at_command('%');assert(!status && reply1==(3300u<<16|25) && adc_calls==1);
 assert(cases==4224);
 puts("PASS READ_AT MCU: 4224 legacy differential + 24 overflow cases, diagnostics and side effects");
}
