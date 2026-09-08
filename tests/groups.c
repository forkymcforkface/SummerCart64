/* Grouped SD register trace model: compare actual stock and candidate
 * register events, responses and failures while checking intended frame savings. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "fpga.h"
#include "sd.h"
#include "types.inc"

/* Decode every actual SPI write at word completion, as mcu_top.sv does.
   Compare externally visible register reads/writes independently of framing.
   Delayed SD command/card busy scripts exercise every response path. */
typedef struct
{
    uint8_t op, reg;
    uint32_t value;
} event_t;
typedef struct
{
    uint8_t bytes[32];
    unsigned length, rx, tx, duplex;
} frame_t;
typedef struct
{
    event_t events[64];
    unsigned events_n;
    frame_t frames[32];
    unsigned frames_n;
    bool active;
} trace_t;
static trace_t trace, baseline;
static uint32_t status_script[16], replies[256];
static unsigned status_n, status_at;
static unsigned cases;
static uint64_t baseline_bytes, candidate_bytes, baseline_frames, candidate_frames;

static void event(uint8_t op, uint8_t reg, uint32_t value)
{
    assert(trace.events_n < 64);
    trace.events[trace.events_n++] = (event_t){op, reg, value};
}
void hw_spi_start(void)
{
    assert(!trace.active && trace.frames_n < 32);
    trace.active = true;
    trace.frames[trace.frames_n++] = (frame_t){0};
}
void hw_spi_stop(void)
{
    assert(trace.active);
    frame_t *f = &trace.frames[trace.frames_n - 1];
    assert(f->length >= 2);
    if (f->bytes[0] == CMD_REG_WRITE)
        assert((f->length - 2) % 4 == 0);
    trace.active = false;
}
void hw_spi_tx(uint8_t *data, int length)
{
    assert(trace.active && length > 0);
    frame_t *f = &trace.frames[trace.frames_n - 1];
    f->tx++;
    const uint8_t *bytes = data;
    for (int i = 0; i < length; i++)
    {
        assert(f->length < sizeof f->bytes);
        f->bytes[f->length++] = bytes[i];
        if (f->length >= 6 && f->bytes[0] == CMD_REG_WRITE && (f->length - 2) % 4 == 0)
        {
            unsigned offset = f->length - 4;
            uint32_t value = (uint32_t)f->bytes[offset] |
                             ((uint32_t)f->bytes[offset + 1] << 8) |
                             ((uint32_t)f->bytes[offset + 2] << 16) |
                             ((uint32_t)f->bytes[offset + 3] << 24);
            event('w', f->bytes[1] + (offset - 2) / 4, value);
        }
    }
}
void hw_spi_rx(uint8_t *data, int length)
{
    assert(trace.active && length == 4);
    frame_t *f = &trace.frames[trace.frames_n - 1];
    assert(f->length == 2 && f->bytes[0] == CMD_REG_READ);
    unsigned reg = f->bytes[1];
    uint32_t value = replies[reg];
    if (reg == REG_SD_SCR)
    {
        assert(status_at < status_n);
        value = status_script[status_at++];
    }
    event('r', reg, value);
    memcpy(data, &value, 4);
    f->rx += 4;
}
/* Reuse the same register-response model, then account for one physical DMA call. */
void hw_spi_transfer(uint8_t *tx, uint8_t *rx, int length)
{
    assert(trace.active && length == 6);
    frame_t *f = &trace.frames[trace.frames_n - 1];
    assert(f->length == 0 && tx[0] == CMD_REG_READ);
    assert(tx[2] == 0 && tx[3] == 0 && tx[4] == 0 && tx[5] == 0);
    hw_spi_tx(tx, 2);
    hw_spi_rx(rx + 2, 4);
    rx[0] = 0xa5;
    rx[1] = 0x5a;
    f->tx = 0;
    f->duplex = 1;
}
#include "functions.inc"

static void reset_trace(void)
{
    trace = (trace_t){0};
    status_at = 0;
}
static void compare(unsigned frames_saved, unsigned bytes_saved)
{
    assert(!trace.active && baseline.events_n == trace.events_n);
    for (unsigned i = 0; i < trace.events_n; i++)
    {
        assert(baseline.events[i].op == trace.events[i].op);
        assert(baseline.events[i].reg == trace.events[i].reg);
        assert(baseline.events[i].value == trace.events[i].value);
    }
    assert(baseline.frames_n == trace.frames_n + frames_saved);
    for (unsigned i = 0; i < baseline.frames_n; i++)
    {
        frame_t *f = &baseline.frames[i];
        assert(f->tx == (f->bytes[0] == CMD_REG_READ ? 2 : 3));
    }
    for (unsigned i = 0; i < trace.frames_n; i++)
    {
        frame_t *f = &trace.frames[i];
        if (f->bytes[0] == CMD_REG_READ)
            assert(f->tx == !EXPECT_DUPLEX && f->rx == 4 && f->duplex == EXPECT_DUPLEX);
    }
    unsigned a = 0, b = 0;
    for (unsigned i = 0; i < baseline.frames_n; i++)
        a += baseline.frames[i].length + baseline.frames[i].rx;
    for (unsigned i = 0; i < trace.frames_n; i++)
        b += trace.frames[i].length + trace.frames[i].rx;
    assert(a == b + bytes_saved);
    baseline_bytes += a;
    candidate_bytes += b;
    baseline_frames += baseline.frames_n;
    candidate_frames += trace.frames_n;
    cases++;
}
static void test_command(uint8_t cmd, uint32_t arg, rsp_type_t type, unsigned busy,
                         bool error, bool response)
{
    status_n = 0;
    for (unsigned i = 0; i < busy; i++)
        status_script[status_n++] = SD_SCR_CMD_BUSY;
    status_script[status_n++] = (error ? SD_SCR_CMD_ERROR : 0);
    if (type == RSP_R1b)
    {
        for (unsigned i = 0; i < busy; i++)
            status_script[status_n++] = SD_SCR_CARD_BUSY;
        status_script[status_n++] = (error ? SD_SCR_CMD_ERROR : 0);
    }
    uint8_t a[24], b[24];
    memset(a, 0xa5, sizeof a);
    memset(b, 0xa5, sizeof b);
    reset_trace();
    bool ar = baseline_sd_cmd(cmd, arg, type, response ? a + 4 : NULL);
    assert(status_at == status_n);
    baseline = trace;
    reset_trace();
    bool br = candidate_sd_cmd(cmd, arg, type, response ? b + 4 : NULL);
    assert(status_at == status_n && ar == br && ar == error);
    assert(memcmp(a, b, sizeof a) == 0);
    compare(1, 2);
    assert(trace.frames[0].length == 10 && trace.frames[0].tx == 2);
    assert(trace.events[0].reg == REG_SD_ARG && trace.events[0].value == arg);
    assert(trace.events[1].reg == REG_SD_CMD);
}
static void test_dma(uint32_t address, uint32_t count, bool read, bool swap)
{
    p.byte_swap = swap;
    reset_trace();
    if (read)
        baseline_sd_dma_start_read(address, count);
    else
        baseline_sd_dma_start_write(address, count);
    baseline = trace;
    reset_trace();
    if (read)
        candidate_sd_dma_start_read(address, count);
    else
        candidate_sd_dma_start_write(address, count);
    compare(2, 4);
    assert(trace.frames_n == 1 && trace.frames[0].length == 14 &&
           trace.frames[0].tx == 2);
    assert(trace.events[0].reg == REG_SD_DMA_ADDRESS &&
           trace.events[0].value == address);
    assert(trace.events[1].reg == REG_SD_DMA_LENGTH &&
           trace.events[1].value == count * 512);
    assert(trace.events[2].reg == REG_SD_DMA_SCR &&
           (trace.events[2].value & DMA_SCR_START));
}
int main(void)
{
    uint32_t endian = 1;
    assert(*(uint8_t *)&endian == 1);
    for (unsigned i = 0; i < 256; i++)
        replies[i] = 0x81234567 ^ (i * 0x01010101u);
    const uint32_t patterns[] = {0,          1,          0xff,       0x100,
                                 0xffff,     0x10000,    0xffffff,   0x1000000,
                                 0x80000000, 0xffffffff, 0x12345678, 0xa55aa55a};
    for (unsigned cmd = 0; cmd < 64; cmd++)
        for (unsigned type = RSP_NONE; type <= RSP_R7; type++)
            for (unsigned v = 0; v < sizeof patterns / sizeof patterns[0]; v++)
                for (unsigned flags = 0; flags < 8; flags++)
                    test_command(cmd, patterns[v], type, flags & 3, flags & 4, v & 1);
    const uint32_t addresses[] = {0,         1,         2,         0x1fffff,
                                  0x3fffffe, 0x4fffffe, 0x4ffffff, 0x5000000,
                                  0x5000001, 0x5002000};
    for (unsigned i = 0; i < sizeof addresses / sizeof addresses[0]; i++)
        for (unsigned n = 1; n <= 256; n++)
            for (unsigned flags = 0; flags < 4; flags++)
                test_dma(addresses[i], n, flags & 1, flags & 2);
    uint32_t seed = 0x87654321;
    for (unsigned i = 0; i < 20000; i++)
    {
        seed ^= seed << 13;
        seed ^= seed >> 17;
        seed ^= seed << 5;
        test_command(seed & 63, seed, seed % 7, (seed >> 9) & 3, (seed >> 7) & 1, true);
        test_dma(seed % 0x05002800, 1 + (seed % 256), seed & 1, seed & 2);
    }
    reset_trace();
    fpga_reg_set_words(REG_SD_ARG, NULL, 0);
    assert(trace.frames_n == 0);
    printf("PASS cases=%u event-identical SD "
           "command/read-response/error/busy/DMA/address/byte-swap sequences\n",
           cases);
    printf(
        "SPI bytes %llu -> %llu; CS frames %llu -> %llu; no hardware timing claimed\n",
        (unsigned long long)baseline_bytes, (unsigned long long)candidate_bytes,
        (unsigned long long)baseline_frames, (unsigned long long)candidate_frames);
}
