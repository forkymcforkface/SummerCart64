/* Isolated N64 diagnostic: compare target ABI output and actual display pixels.
   The generator inserts this fixture only into an explicit test destination. */
#include <stdarg.h>
#include <limits.h>
#include "display.h"
#include "interrupts.h"
extern bool research_original_formatter;
extern volatile uint32_t *research_display_pixels(void);
extern int npf_vsnprintf(char *,size_t,const char *,va_list);
static uint32_t research_reference_pixels[640*240];
static unsigned research_format_cases,research_format_errors;
static void research_format_check(size_t n,const char *fmt,...){
 unsigned char a[280],b[280];memset(a,0xA5,sizeof a);memset(b,0xA5,sizeof b);
 va_list x,y;va_start(x,fmt);va_copy(y,x);
 int ra=vsniprintf((char *)a+8,n,fmt,x),rb=npf_vsnprintf((char *)b+8,n,fmt,y);va_end(x);va_end(y);
 size_t used=n?(ra<(int)n?(size_t)(ra+1):n):0;
 if(ra!=rb||memcmp(a,b,8+used)||memcmp(a+8+n,b+8+n,sizeof a-8-n))research_format_errors++;
 research_format_cases++;
}
static void research_draw_suite(unsigned sample){
 uint32_t u=sample==0?0:sample==1?0xFFFFFFFFu:sample==2?0x80000000u:0x12345678u;
 int v=(int)u;unsigned long long big=((unsigned long long)u<<32)|~u;
 display_init();
 display_printf("SC64 diagnostic format ABI comparison\n");
 display_printf("%01d %02d %03d %04d %2d %3d %d\n",v,v,v,v,v,v,v);
 display_printf("%02X %08X %08lX\n",u,u,(unsigned long)u);
 display_printf("%016lX %016llX %ld\n",(unsigned long)u,big,(long)v);
 display_printf("%c [%s]\n",'Q',"error/watchdog/exception text");
 display_printf("signed64: %lld unsigned64: %llu\n",(long long)big,big);
 display_printf(" > 0x%016llX (W) != 0x%016llX (R)\n",big,~big);
 display_printf(" pc: 0x%08lX sr: 0x%08lX\n",(unsigned long)u,~(unsigned long)u);
 /* Preserve the existing exception call's argument/format mismatch in this
    comparison: the production %016lX consumes a 32-bit long on this ABI. */
 display_printf("legacy hi: 0x%016lX\n",big);
}
static void research_formatter_diagnostic(void){
 interrupts_stop_watchdog();
 char longstr[600];memset(longstr,'Z',599);longstr[599]=0;
 const size_t caps[]={0,1,2,7,255,256,257};
 const uint32_t values[]={0,1,9,10,99,0x7FFFFFFF,0x80000000,0xFFFFFFFF,0x12345678};
 const char *ints[]={"%01d","%02d","%03d","%04d","%2d","%3d","%d"};
 for(unsigned k=0;k<sizeof caps/sizeof *caps;k++)for(unsigned j=0;j<sizeof values/sizeof *values;j++){
  uint32_t u=values[j];int v=(int)u;size_t n=caps[k];unsigned long long big=((unsigned long long)u<<32)|~u;
  for(unsigned f=0;f<sizeof ints/sizeof *ints;f++)research_format_check(n,ints[f],v);
  research_format_check(n,"%02X",u);research_format_check(n,"%08X",u);research_format_check(n,"%08lX",(unsigned long)u);research_format_check(n,"%016lX",(unsigned long)u);
  research_format_check(n,"%016llX",big);research_format_check(n,"%ld",(long)v);research_format_check(n,"%c",(int)(u&255));research_format_check(n,"%s",j&1?longstr:"");
  research_format_check(n,"%lld %llu",(long long)big,big);research_format_check(n,"%lld",LLONG_MIN);research_format_check(n,"%llu",ULLONG_MAX);
  research_format_check(n," hi: 0x%016lX\n",big);
 }
 unsigned mismatches=0,reference_white=0,candidate_white=0;
 volatile uint32_t *pixels=research_display_pixels();
 for(unsigned sample=0;sample<4;sample++){
  research_original_formatter=true;research_draw_suite(sample);
  for(unsigned i=0;i<640*240;i++){research_reference_pixels[i]=pixels[i];reference_white+=pixels[i]==UINT32_MAX;}
  research_original_formatter=false;research_draw_suite(sample);
  for(unsigned i=0;i<640*240;i++){if(research_reference_pixels[i]!=pixels[i])mismatches++;candidate_white+=pixels[i]==UINT32_MAX;}
 }
 display_printf("NEGATIVE CONTROL");
 unsigned negative_mismatches=0;
 for(unsigned i=0;i<640*240;i++)if(research_reference_pixels[i]!=pixels[i])negative_mismatches++;
 bench_report("framebuffer_address",(uint32_t)pixels);
 bench_report("baseline_white_pixels",reference_white);
 bench_report("candidate_white_pixels",candidate_white);
 bench_report("negative_control_word_errors",negative_mismatches);
 bench_report("format_cases",research_format_cases);
 bench_report("format_errors",research_format_errors);
 bench_report("framebuffer_word_errors",mismatches);
 bench_report("long_bytes",sizeof(long));
 bench_report("longlong_bytes",sizeof(long long));
 interrupts_start_watchdog();
}

