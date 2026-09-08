/* Bounded menu reader on actual FatFs with a RAM disk and a mapped cart
 * destination. Physical media and hardware DMA are replaced by host callbacks. */
#define _GNU_SOURCE
#include "ff.h"
#include "diskio.h"
#include <assert.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
#define ROM_ADDRESS 0x10000000u
#define SECTORS 262144u
static unsigned char *disk;
static int reads, fail_read, direct;
static FATFS fs;
static unsigned alloc_unit = 512;
static void check(FRESULT r, const char *what)
{
    if (r)
    {
        fprintf(stderr, "%s: error %d\n", what, r);
        exit(1);
    }
}
DSTATUS disk_initialize(BYTE p) { return p ? STA_NODISK : 0; }
DSTATUS disk_status(BYTE p) { return p ? STA_NODISK : 0; }
DRESULT disk_read(BYTE p, BYTE *b, LBA_t s, UINT n)
{
    if (p || (uint64_t)s + n > SECTORS)
        return RES_PARERR;
    if (++reads == fail_read)
        return RES_ERROR;
    memcpy(b, disk + s * 512, n * 512);
    return RES_OK;
}
DRESULT disk_write(BYTE p, const BYTE *b, LBA_t s, UINT n)
{
    if (p || (uint64_t)s + n > SECTORS)
        return RES_PARERR;
    memcpy(disk + s * 512, b, n * 512);
    return RES_OK;
}
DRESULT disk_ioctl(BYTE p, BYTE c, void *b)
{
    if (p)
        return RES_PARERR;
    switch (c)
    {
    case CTRL_SYNC:
        return RES_OK;
    case GET_SECTOR_COUNT:
        *(LBA_t *)b = SECTORS;
        return RES_OK;
    case GET_SECTOR_SIZE:
        *(WORD *)b = 512;
        return RES_OK;
    case GET_BLOCK_SIZE:
        *(DWORD *)b = 1;
        return RES_OK;
    default:
        return RES_PARERR;
    }
}
DWORD get_fattime(void) { return (46u << 25) | (1u << 21) | (1u << 16); }
#define SC64_OK 0
static int sc64_error_fatfs;
static int boundary_mode;
static uint32_t boundary_sector, boundary_count;
static int sc64_sd_read_sectors(void *b, uint32_t s, uint32_t n)
{
    direct++;
    if (boundary_mode)
    {
        boundary_sector = s;
        boundary_count = n;
        return 0;
    }
    return disk_read(0, b, s, n) != RES_OK;
}
#include "menu_snapshot.inc"
static void mount_new(int exfat)
{
    f_mount(NULL, "", 0);
    memset(disk, 0, SECTORS * 512u);
    reads = fail_read = 0;
    MKFS_PARM m = {.fmt = (exfat ? FM_EXFAT : FM_FAT32) | FM_SFD,
                   .n_fat = 1,
                   .align = 1,
                   .n_root = 0,
                   .au_size = alloc_unit};
    unsigned char work[8192];
    check(f_mkfs("", &m, work, sizeof work), "mkfs");
    check(f_mount(&fs, "", 1), "mount");
    printf("format=%s cluster_sectors=%u\n", exfat ? "exfat" : "fat32", fs.csize);
}
static void make_file(unsigned parts, int fragmented, unsigned tail)
{
    FIL target, block;
    UINT n;
    check(f_open(&target, "sc64menu.n64", FA_CREATE_ALWAYS | FA_WRITE), "create");
    unsigned size = fs.csize * 512;
    unsigned char *data = malloc(size);
    for (unsigned i = 0; i < parts; i++)
    {
        for (unsigned j = 0; j < size; j++)
            data[j] = (i * 31 + j * 17 + 3) & 255;
        unsigned len = (i + 1 == parts && tail) ? tail : size;
        check(f_write(&target, data, len, &n), "write");
        assert(n == len);
        check(f_sync(&target), "sync");
        if (fragmented)
        {
            char name[32];
            snprintf(name, sizeof name, "block%03u.bin", i);
            check(f_open(&block, name, FA_CREATE_ALWAYS | FA_WRITE), "block create");
            check(f_write(&block, data, size, &n), "block write");
            assert(n == size);
            check(f_close(&block), "block close");
        }
    }
    check(f_close(&target), "close");
    free(data);
}
static void open_menu(FIL *f)
{
    check(f_mount(NULL, "", 0), "unmount");
    check(f_mount(&fs, "", 1), "remount");
    check(f_open(f, "sc64menu.n64", FA_READ), "open");
    f->obj.objsize = (f_size(f) + 511) & ~(FSIZE_t)511;
}
static void run_case(int exfat, unsigned parts, int fragmented, unsigned tail)
{
    mount_new(exfat);
    make_file(parts, fragmented, tail);
    FIL f;
    open_menu(&f);
    UINT n = 0;
    size_t size = f_size(&f);
    unsigned char *expected = malloc(size ? size : 1);
    reads = 0;
    check(f_read(&f, expected, size, &n), "original read");
    assert(n == size);
    int original_reads = reads;
    check(f_close(&f), "original close");
    open_menu(&f);
    reads = direct = 0;
    memset((void *)(uintptr_t)ROM_ADDRESS, 0xcc, size);
    check(menu_read(&f, &n), "candidate read");
    assert(n == size);
    assert(!memcmp(expected, (void *)(uintptr_t)ROM_ADDRESS, size));
    int candidate_reads = reads, dc = direct;
    check(f_close(&f), "candidate close");
    if (fragmented && parts == 63)
        assert(dc == 63);
    if (fragmented && parts == 64)
        assert(dc == 0);
    for (int fail = 1; fail <= candidate_reads; fail++)
    {
        open_menu(&f);
        reads = direct = 0;
        fail_read = fail;
        FRESULT r = menu_read(&f, &n);
        fail_read = 0;
        if (r != FR_DISK_ERR)
        {
            fprintf(stderr, "failure index %d result %d\n", fail, r);
            exit(1);
        }
        f_close(&f);
    }
    printf("PASS fs=%s parts=%u fragment=%d tail=%u bytes=%zu original_reads=%d "
           "candidate_reads=%d direct=%d injected_errors=%d\n",
           exfat ? "exfat" : "fat32", parts, fragmented, tail, size, original_reads,
           candidate_reads, dc, candidate_reads);
    fflush(stdout);
    free(expected);
}

static void timeout_exit(int sig)
{
    (void)sig;
    _exit(99);
}
static void test_bounds(void)
{
    FIL f;
    memset(&f, 0, sizeof f);
    UINT n = 0;
    f.obj.objsize = 0x04000001u;
    reads = direct = 0;
    assert(menu_read(&f, &n) == FR_INVALID_PARAMETER);
    assert(reads == 0 && direct == 0);
    f.obj.objsize = UINT64_C(0x20000000000);
    assert(menu_read(&f, &n) == FR_INVALID_PARAMETER);
    assert(reads == 0 && direct == 0);
    puts("PASS oversized bounds reject before I/O");
}
static void test_cycle(int exfat, unsigned parts)
{
    mount_new(exfat);
    make_file(parts, exfat, 0);
    FIL f;
    open_menu(&f);
    DWORD cluster = f.obj.sclust;
    LBA_t fat = fs.fatbase;
    check(f_close(&f), "close cycle");
    unsigned char *entry = disk + fat * 512 + cluster * 4;
    entry[0] = cluster;
    entry[1] = cluster >> 8;
    entry[2] = cluster >> 16;
    entry[3] = cluster >> 24;
    open_menu(&f);
    unsigned char b[2048];
    UINT n;
    check(f_read(&f, b, parts * 512, &n), "cycle original");
    assert(n == parts * 512);
    check(f_close(&f), "cycle original close");
    fflush(NULL);
    pid_t pid = fork();
    assert(pid >= 0);
    if (!pid)
    {
        signal(SIGALRM, timeout_exit);
        alarm(1);
        open_menu(&f);
        FRESULT r = menu_read(&f, &n);
        if (r != FR_OK || n != parts * 512 ||
            memcmp(b, (void *)(uintptr_t)ROM_ADDRESS, parts * 512))
            _exit(2);
        _exit(0);
    }
    int st;
    waitpid(pid, &st, 0);
    assert(WIFEXITED(st) && WEXITSTATUS(st) == 0);
    printf("PASS %s cycle parts=%u bounded candidate byte-matches original\n",
           exfat ? "exfat" : "fat32", parts);
}

static void test_bad_chain(int exfat, DWORD value)
{
    mount_new(exfat);
    make_file(2, exfat, 0);
    FIL f;
    open_menu(&f);
    DWORD cluster = f.obj.sclust;
    LBA_t fat = fs.fatbase;
    check(f_close(&f), "bad chain close");
    unsigned char *entry = disk + fat * 512 + cluster * 4;
    entry[0] = value;
    entry[1] = value >> 8;
    entry[2] = value >> 16;
    entry[3] = value >> 24;
    open_menu(&f);
    unsigned char b[1024];
    UINT n;
    FRESULT a = f_read(&f, b, sizeof b, &n);
    assert(a == FR_INT_ERR);
    f_close(&f);
    open_menu(&f);
    FRESULT c = menu_read(&f, &n);
    assert(c == FR_INT_ERR);
    f_close(&f);
    printf("PASS corrupt FAT next=%08x original=%d candidate=%d\n", value, a, c);
}

static void test_map_scope(void)
{
    mount_new(0);
    make_file(2, 0, 0);
    FIL f;
    DWORD map[128];
    check(f_open(&f, "sc64menu.n64", FA_READ | FA_WRITE), "writable open");
    f.obj.objsize = 512;
    map[0] = 128;
    f.cltbl = map;
    check(f_lseek(&f, CREATE_LINKMAP), "writable map");
    assert(map[1] == 2);
    f.cltbl = NULL;
    f_close(&f);
    open_menu(&f);
    f.obj.objsize = 512;
    map[0] = 128;
    f.cltbl = map;
    check(f_lseek(&f, CREATE_LINKMAP), "readonly map");
    assert(map[1] == 1);
    f.cltbl = NULL;
    f_close(&f);
    open_menu(&f);
    f.obj.sclust = fs.n_fatent;
    UINT n;
    assert(menu_read(&f, &n) == FR_INT_ERR);
    f_close(&f);
    puts("PASS writable full-chain map preserved; readonly bounded; invalid start "
         "rejected");
}

static void test_max_size(void)
{
    mount_new(0);
    FIL f;
    UINT n;
    unsigned char block[65536];
    for (unsigned i = 0; i < sizeof block; i++)
        block[i] = (i * 17 + 31) & 255;
    check(f_open(&f, "sc64menu.n64", FA_CREATE_ALWAYS | FA_WRITE), "max create");
    for (unsigned i = 0; i < 1024; i++)
    {
        check(f_write(&f, block, sizeof block, &n), "max write");
        assert(n == sizeof block);
    }
    check(f_close(&f), "max close");
    open_menu(&f);
    unsigned char *expected = malloc(0x04000000);
    assert(expected);
    check(f_read(&f, expected, 0x04000000, &n), "max original");
    assert(n == 0x04000000);
    check(f_close(&f), "max original close");
    open_menu(&f);
    check(menu_read(&f, &n), "max candidate");
    assert(n == 0x04000000 && !memcmp(expected, (void *)(uintptr_t)ROM_ADDRESS, n));
    check(f_close(&f), "max candidate close");
    free(expected);
    puts("PASS exact64MiB FAT32 candidate byte-matches original");
}

static void test_empty_and_invalid_start(void)
{
    mount_new(0);
    make_file(0, 0, 0);
    FIL f;
    UINT n = 99;
    open_menu(&f);
    reads = direct = 0;
    check(menu_read(&f, &n), "empty menu");
    assert(n == 0 && direct == 0);
    check(f_close(&f), "empty close");
    make_file(1, 0, 0);
    DWORD invalid[] = {0, 1, fs.n_fatent, 0xffffffff};
    for (unsigned i = 0; i < sizeof invalid / sizeof *invalid; i++)
    {
        open_menu(&f);
        f.obj.sclust = invalid[i];
        reads = direct = 0;
        n = 99;
        assert(menu_read(&f, &n) == FR_INT_ERR);
        assert(direct == 0);
        f_close(&f);
    }
    puts("PASS empty menu and invalid start clusters reject before direct read");
}
static void test_unused_bad_next(void)
{
    for (int exfat = 0; exfat < 2; exfat++)
    {
        mount_new(exfat);
        make_file(1, 0, 0);
        FIL f;
        open_menu(&f);
        DWORD cluster = f.obj.sclust;
        LBA_t fat = fs.fatbase;
        f_close(&f);
        memset(disk + fat * 512 + cluster * 4, 0, 4);
        open_menu(&f);
        unsigned char expected[512];
        UINT n;
        check(f_read(&f, expected, sizeof expected, &n), "bad tail original");
        assert(n == 512);
        f_close(&f);
        open_menu(&f);
        check(menu_read(&f, &n), "bad tail candidate");
        assert(n == 512 && !memcmp(expected, (void *)(uintptr_t)ROM_ADDRESS, 512));
        f_close(&f);
    }
    puts("PASS unused invalid successor beyond EOF does not change read behavior");
}
static void test_lba_boundary(void)
{
    assert(sizeof(LBA_t) == 4);
    mount_new(0);
    make_file(2, 0, 0);
    FIL f;
    UINT n;
    open_menu(&f);
    LBA_t database = fs.database;
    uint64_t offset = (uint64_t)(f.obj.sclust - 2) * fs.csize;
    assert(offset > 0 && offset < UINT32_MAX);
    fs.database = UINT32_MAX - offset;
    f.obj.objsize = 512;
    boundary_mode = 1;
    direct = 0;
    check(menu_read(&f, &n), "last representable sector");
    assert(n == 512 && direct == 1 && boundary_sector == UINT32_MAX &&
           boundary_count == 1);
    f.obj.objsize = 1024;
    direct = 0;
    assert(menu_read(&f, &n) == FR_INVALID_PARAMETER);
    assert(direct == 0);
    f.obj.objsize = 512;
    fs.database = UINT32_MAX;
    direct = 0;
    assert(menu_read(&f, &n) == FR_INVALID_PARAMETER);
    assert(direct == 0);
    boundary_mode = 0;
    fs.database = database;
    f_close(&f);
    puts("PASS LBA32 last sector accepted; crossing/end-start overflow rejected before "
         "direct read");
}

int main(void)
{
    disk = calloc(SECTORS, 512);
    assert(disk);
    void *p =
        mmap((void *)(uintptr_t)ROM_ADDRESS, 64u * 1024 * 1024, PROT_READ | PROT_WRITE,
             MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
    assert(p == (void *)(uintptr_t)ROM_ADDRESS);
    for (int e = 0; e < 2; e++)
    {
        run_case(e, 1, 0, 511);
        run_case(e, 1, 0, 0);
        run_case(e, 2, 0, 1);
        run_case(e, 32, 0, 0);
        run_case(e, 5, 1, 17);
        run_case(e, 63, 1, 0);
        run_case(e, 64, 1, 0);
    }
    alloc_unit = 1024;
    run_case(0, 32, 0, 0);
    run_case(0, 5, 1, 17);
    alloc_unit = 4096;
    run_case(1, 32, 0, 0);
    run_case(1, 5, 1, 17);
    alloc_unit = 512;
    test_empty_and_invalid_start();
    test_unused_bad_next();
    test_lba_boundary();
    test_max_size();
    test_map_scope();
    test_bounds();
    test_bad_chain(0, 0);
    test_bad_chain(0, 1);
    test_bad_chain(0, 0x0fffffff);
    test_bad_chain(1, 0);
    test_bad_chain(1, 1);
    test_bad_chain(1, 0x7fffffff);
    test_cycle(0, 1);
    test_cycle(0, 4);
    test_cycle(1, 4);
    free(disk);
    munmap(p, 64u * 1024 * 1024);
    puts("FIXTURE CHECKS PASS; HARDWARE NOT TESTED");
    return 0;
}
