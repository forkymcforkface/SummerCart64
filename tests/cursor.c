/* Cursor command model: compare actual stock and candidate functions under
 * identical command failures, cursor jumps, writes, resets and wraparound. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef unsigned sc64_error_t;
typedef unsigned sc64_sd_card_status_t;
enum
{
    SC64_OK,
    ERR_LOCK,
    ERR_INIT,
    ERR_SET,
    ERR_IO,
    ERR_ARG
};
enum
{
    CMD_ID_SD_CARD_OP,
    CMD_ID_SD_SECTOR_SET,
    CMD_ID_SD_READ,
    CMD_ID_SD_WRITE
};
enum
{
    SD_CARD_OP_INIT,
    SD_CARD_OP_DEINIT,
    SD_CARD_OP_GET_STATUS,
    SD_CARD_OP_GET_INFO,
    SD_CARD_OP_BYTE_SWAP_ON,
    SD_CARD_OP_BYTE_SWAP_OFF
};
typedef struct
{
    unsigned id;
    uint32_t arg[2], rsp[2];
} sc64_cmd_t;
static bool sc64_sector_cache_test;
#include "cursor-state.inc"
static uint32_t device_sector;
static bool locked, initialized;
static int fail_set, fail_io;
static unsigned sets, reads, writes, partial;
typedef struct
{
    unsigned id;
    uint32_t sector, count;
    unsigned result, partial;
} io_t;
static io_t events[50000];
static unsigned event_count;
static sc64_error_t sc64_execute_cmd(sc64_cmd_t *c)
{
    if (c->id == CMD_ID_SD_CARD_OP)
    {
        switch (c->arg[1])
        {
        case SD_CARD_OP_INIT:
            locked = initialized = true;
            return SC64_OK;
        case SD_CARD_OP_DEINIT:
            locked = initialized = false;
            return SC64_OK;
        case SD_CARD_OP_GET_STATUS:
            c->rsp[1] = initialized ? 3 : 1;
            return SC64_OK;
        default:
            return locked ? SC64_OK : ERR_LOCK;
        }
    }
    if (c->id == CMD_ID_SD_SECTOR_SET)
    {
        sets++;
        if (!locked)
            return ERR_LOCK;
        if (fail_set)
        {
            fail_set = 0;
            return ERR_SET;
        }
        device_sector = c->arg[0];
        return SC64_OK;
    }
    unsigned e = SC64_OK;
    uint32_t count = c->arg[1];
    if (!locked)
        e = ERR_LOCK;
    else if (!initialized)
        e = ERR_INIT;
    else if (!count || count >= 0x800000)
        e = ERR_ARG;
    else if (fail_io)
    {
        fail_io = 0;
        e = ERR_IO;
    }
    unsigned done = e == ERR_IO ? count / 2 : 0;
    if (e != ERR_LOCK)
        events[event_count++] = (io_t){c->id, device_sector, count, e, done};
    assert(event_count < 50000);
    if (c->id == CMD_ID_SD_READ)
        reads++;
    else
        writes++;
    partial += done;
    if (!e)
        device_sector += count;
    return e;
}
#include "snapshot.inc"
static unsigned status_count;
static unsigned statuses[50000];
static void record(unsigned r)
{
    statuses[status_count++] = r;
    assert(status_count < 50000);
}
static void rd(uint32_t s, uint32_t n)
{
    record(sc64_sd_read_sectors((void *)(uintptr_t)0x10000000, s, n));
}
static void wr(uint32_t s, uint32_t n)
{
    record(sc64_sd_write_sectors((void *)(uintptr_t)0x10000000, s, n));
}
static void setup(bool cache)
{
    sc64_sector_cache_test = cache;
    sector_known = false;
    sector_next = device_sector = 0;
    locked = initialized = false;
    fail_set = fail_io = 0;
    sets = reads = writes = partial = event_count = status_count = 0;
    memset(events, 0, sizeof events);
}
static void sequence(void)
{
    record(sc64_sd_card_init());
    rd(100, 2);
    rd(102, 3);
    rd(105, 1);
    rd(40, 1);
    rd(41, 1);
    wr(300, 2);
    rd(302, 1);
    rd(303, 1);
    record(sc64_sd_card_deinit());
    record(sc64_sd_card_init());
    rd(304, 1);
    rd(305, 1);
    fail_set = 1;
    rd(900, 3);
    rd(900, 3);
    rd(903, 1);
    fail_io = 1;
    rd(904, 8);
    rd(904, 8);
    rd(912, 1);
    locked = initialized = false;
    device_sector = 0;
    rd(913, 1);
    record(sc64_sd_card_init());
    rd(913, 1);
    rd(914, 1);
    rd(UINT32_MAX, 1);
    rd(0, 1);
    rd(1, 1);
    rd(2, 0);
    rd(2, 1);
    unsigned status;
    record(sc64_sd_card_get_status(&status));
    record(sc64_sd_set_byte_swap(true));
    record(sc64_sd_card_get_info((void *)(uintptr_t)0x10000000));
    rd(3, 1);
    uint32_t state = 0x12345678, sector = 5000;
    for (unsigned i = 0; i < 10000; i++)
    {
        state ^= state << 13;
        state ^= state >> 17;
        state ^= state << 5;
        unsigned n = 1 + (state & 7);
        switch ((state >> 8) % 12)
        {
        case 0:
            wr(sector, n);
            break;
        case 1:
            record(sc64_sd_card_deinit());
            record(sc64_sd_card_init());
            rd(sector, n);
            break;
        case 2:
            fail_io = 1;
            rd(sector, n);
            rd(sector, n);
            break;
        case 3:
            sector = state & 0xffff;
            rd(sector, n);
            break;
        default:
            rd(sector, n);
            break;
        }
        sector += n;
    }
}
int main(void)
{
    setup(false);
    sequence();
    unsigned ns = status_count, ne = event_count, base_sets = sets;
    unsigned *saved = malloc(ns * sizeof *saved);
    io_t *ev = malloc(ne * sizeof *ev);
    memcpy(saved, statuses, ns * sizeof *saved);
    memcpy(ev, events, ne * sizeof *ev);
    setup(true);
    sequence();
    assert(status_count == ns && event_count == ne);
    assert(!memcmp(saved, statuses, ns * sizeof *saved));
    assert(!memcmp(ev, events, ne * sizeof *ev));
    assert(sets < base_sets);
    printf("PASS status=%u io=%u SET baseline=%u cached=%u saved=%u "
           "partial_failure_sectors=%u\n",
           ns, ne, base_sets, sets, base_sets - sets, partial);
    setup(true);
    assert(!sc64_sd_card_init());
    rd(10, 1);
    assert(sets == 1);
    rd(11, 1);
    assert(sets == 1);
    fail_io = 1;
    rd(12, 4);
    assert(!sector_known);
    rd(12, 4);
    assert(sets == 2);
    wr(100, 1);
    assert(!sector_known && sets == 3);
    rd(101, 1);
    assert(sets == 4);
    assert(!sc64_sd_card_deinit() && !sector_known);
    assert(!sc64_sd_card_init());
    rd(102, 1);
    assert(sets == 5);
    fail_set = 1;
    rd(900, 1);
    assert(!sector_known);
    rd(900, 1);
    assert(sets == 7);
    locked = initialized = false;
    device_sector = 0;
    rd(901, 1);
    assert(!sector_known);
    assert(!sc64_sd_card_init());
    rd(901, 1);
    assert(sets == 8);
    puts("PASS exact invalidation and retry SET assertions; reset lock loss, partial "
         "read errors, init/deinit/write, wrap");
    free(saved);
    free(ev);
    return 0;
}
