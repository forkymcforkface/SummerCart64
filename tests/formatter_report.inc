/* Bounded diagnostic transport avoids linking printf into timing-only probes.
   Every transfer completes before its single static buffer is reused. */
static unsigned char bench_buffer[256] __attribute__((aligned(16)));
static uint32_t bench_us(uint32_t ticks) { return (uint64_t)ticks * 1000000 / 46875000; }
static void bench_report(const char *key, uint32_t us) {
    bool busy;
    char *p=(char *)bench_buffer;
    const char *prefix="[scboot] ";
    while (*prefix) *p++=*prefix++;
    while (*key) *p++=*key++;
    *p++='=';
    char digits[10]; unsigned used=0;
    do { digits[used++]='0'+us%10; us/=10; } while(us);
    while (used) *p++=digits[--used];
    *p++='\n';
    int n=p-(char *)bench_buffer;
    do { sc64_usb_write_busy(&busy); } while (busy);
    pi_dma_write((io32_t *)SC64_BUFFERS->BUFFER,bench_buffer,(n+7)&~7);
    sc64_usb_write((void *)SC64_BUFFERS->BUFFER,1,n);
    do { sc64_usb_write_busy(&busy); } while (busy);
}
