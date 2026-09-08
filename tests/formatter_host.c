/* Compare the current diagnostic formatter and bounded display wrapper with
   libc, including truncation guards and the production format vocabulary. */
#include <stdio.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>
#include <limits.h>
/*SOURCE_FORMATTER*/
static unsigned checks;
static void check(size_t n,const char *fmt,...){
 unsigned char a[280],b[280];memset(a,0xA5,sizeof a);memset(b,0xA5,sizeof b);
 va_list x,y,z;va_start(x,fmt);va_copy(y,x);va_copy(z,x);
 int ra=vsnprintf((char*)a+8,n,fmt,x),rb=npf_vsnprintf((char*)b+8,n,fmt,y);va_end(x);va_end(y);
 if(n==256){display_vprintf(fmt,z);if(strcmp(captured,(char *)a+8)){fprintf(stderr,"wrapper mismatch\n");exit(1);}}va_end(z);
 if(ra!=rb||memcmp(a,b,8+(n?(ra<(int)n?(size_t)(ra+1):n):0))||memcmp(a+8+n,b+8+n,sizeof a-8-n)){fprintf(stderr,"mismatch %s n=%zu returns=%d/%d\n",fmt,n,ra,rb);exit(1);}checks++;
}
int main(void){char longstr[600];memset(longstr,'Z',599);longstr[599]=0;uint32_t rng=0x31415926;
 size_t caps[]={0,1,2,7,255,256,257};const char *ints[]={"%01d","%02d","%03d","%04d","%2d","%3d","%d"};
 for(unsigned k=0;k<sizeof caps/sizeof *caps;k++)for(unsigned j=0;j<4096;j++){
  rng=rng*1664525u+1013904223u;int v=(int)rng;size_t n=caps[k];
  for(unsigned f=0;f<sizeof ints/sizeof *ints;f++)check(n,ints[f],v);
  check(n,"%02X",rng);check(n,"%08X",rng);check(n,"%08lX",(unsigned long)rng);check(n,"%016lX",(unsigned long)rng);
  check(n,"%016llX",((unsigned long long)rng<<32)|~rng);check(n,"%ld",(long)v);check(n,"%c",(int)(rng&255));
  check(n,"%s",j&1?longstr:"");check(n," > 0x%016llX (W) != 0x%016llX (R)",ULLONG_MAX,0ULL);
  check(n,"Command CONFIG_SET [BOOTLOADER_SWITCH] failed\n (%08X) - %s",rng,"SD card error");
  check(n,"SC64 Test suite (%d / %d)\n\n",v,INT_MAX);check(n," pc: 0x%08lX  sr: 0x%08lX  cr: 0x%08lX  va: 0x%08lX\n",(unsigned long)rng,0UL,(unsigned long)UINT32_MAX,7UL);
 }
 for(unsigned k=0;k<sizeof caps/sizeof *caps;k++){check(caps[k],"%d",INT_MIN);check(caps[k],"%d",INT_MAX);check(caps[k],"%ld",LONG_MIN);check(caps[k],"%ld",LONG_MAX);}
 printf("PASS %u differential formatter cases; full format token inventory, truncation, bounds, signed extremes,64-bit test words\n",checks);return 0;}

