/* SPI register helper trace model: compare actual stock and candidate
 * byte streams, CS lifetimes, return values and DMA-helper call counts. */
#include "fpga.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct
{
    uint8_t bytes[16];
    unsigned len, tx, rx, duplex, start, stop;
    int active;
} trace_t;
static trace_t trace;
static uint32_t reply;
static uint16_t header_garbage;
void hw_spi_start(void)
{
    assert(!trace.active);
    trace.active = 1;
    trace.start++;
}
void hw_spi_stop(void)
{
    assert(trace.active);
    trace.active = 0;
    trace.stop++;
}
void hw_spi_tx(uint8_t *p, int n)
{
    assert(trace.active && n > 0 && trace.len + n <= 16);
    memcpy(trace.bytes + trace.len, p, n);
    trace.len += n;
    trace.tx++;
}
void hw_spi_rx(uint8_t *p, int n)
{
    assert(trace.active && n == 4);
    assert(trace.len == 2 && trace.bytes[0] == CMD_REG_READ);
    memset(trace.bytes + trace.len, 0, 4);
    trace.len += 4;
    memcpy(p, &reply, 4);
    trace.rx++;
}
/* Full-duplex RX includes unspecified header bytes; the data word starts at two. */
void hw_spi_transfer(uint8_t *tx, uint8_t *rx, int n)
{
    assert(trace.active && trace.len == 0 && n == 6);
    assert(tx[0] == CMD_REG_READ && tx[2] == 0 && tx[3] == 0 && tx[4] == 0 && tx[5] == 0);
    memcpy(trace.bytes, tx, 6);
    trace.len = 6;
    trace.duplex++;
    rx[0] = header_garbage;
    rx[1] = header_garbage >> 8;
    memcpy(rx + 2, &reply, 4);
}
#include "baseline.inc"
#include "candidate.inc"
static unsigned cases;
static void test(uint32_t reg, uint32_t value)
{
    trace = (trace_t){0};
    baseline_set((fpga_reg_t)reg, value);
    trace_t a = trace;
    trace = (trace_t){0};
    candidate_set((fpga_reg_t)reg, value);
    trace_t b = trace;
    assert(a.start == 1 && a.stop == 1 && b.start == 1 && b.stop == 1 && !a.active &&
           !b.active);
    assert(a.len == 6 && b.len == 6 && !memcmp(a.bytes, b.bytes, 6));
    assert(a.tx == 3 && b.tx == EXPECT_WRITE_TX && !a.rx && !b.rx);
    uint8_t expected[6] = {CMD_REG_WRITE, reg,         value,
                           value >> 8,    value >> 16, value >> 24};
    assert(!memcmp(b.bytes, expected, 6));
    reply = value;
    trace = (trace_t){0};
    uint32_t av = baseline_get((fpga_reg_t)reg);
    a = trace;
    trace = (trace_t){0};
    uint32_t bv = candidate_get((fpga_reg_t)reg);
    b = trace;
    assert(av == value && bv == value && a.start == 1 && b.start == 1 && a.stop == 1 &&
           b.stop == 1 && !a.active && !b.active);
    assert(a.len == 6 && b.len == 6 && !memcmp(a.bytes, b.bytes, 6));
    assert(a.bytes[0] == CMD_REG_READ && a.bytes[1] == (uint8_t)reg);
    assert(a.tx == 2 && a.rx == 1 && !a.duplex);
    assert(b.duplex == EXPECT_DUPLEX);
    assert(b.tx == (EXPECT_DUPLEX ? 0 : EXPECT_READ_TX) && b.rx == !EXPECT_DUPLEX);
    cases++;
}
int main(void)
{
    uint32_t endian = 1;
    assert(*(uint8_t *)&endian == 1);
    uint32_t values[] = {0,          1,          0xff,       0x100,
                         0xffff,     0x10000,    0xffffff,   0x1000000,
                         0x80000000, 0xffffffff, 0x12345678, 0xa55aa55a};
    for (unsigned r = 0; r < 256; r++)
        for (unsigned v = 0; v < sizeof values / sizeof *values; v++)
            test(r, values[v]);
    for (unsigned h = 0; h < 65536; h++)
    {
        header_garbage = h;
        test(h, 0xa55aa55a ^ (h * 65537u));
    }
    uint32_t state = 0x12345678;
    for (unsigned i = 0; i < 100000; i++)
    {
        state ^= state << 13;
        state ^= state >> 17;
        state ^= state << 5;
        test(state, state ^ 0x87654321);
    }
    printf("PASS cases=%u operations=%u exact byte order, CS boundaries, read values\n",
           cases, cases * 2);
    printf("Candidate TX calls write=%d split-read=%d duplex=%d; no hardware timing claimed.\n",
           EXPECT_WRITE_TX, EXPECT_READ_TX, EXPECT_DUPLEX);
    return 0;
}
