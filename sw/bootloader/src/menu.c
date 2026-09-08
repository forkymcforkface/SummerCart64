#include "error.h"
#include "fatfs/ff.h"
#include "io.h"
#include "menu.h"
#include "sc64.h"


#define ROM_ADDRESS     (0x10000000)


extern sc64_error_t sc64_error_fatfs;


static const char *fatfs_error_codes[] = {
    "No error",
    "A hard error occurred in the low level disk I/O layer",
    "Assertion failed",
    "The physical drive cannot work",
    "Could not find the file",
    "Could not find the path",
    "The path name format is invalid",
    "Access denied due to prohibited access or directory full",
    "Access denied due to prohibited access",
    "The file/directory object is invalid",
    "The physical drive is write protected",
    "The logical drive number is invalid",
    "The volume has no work area",
    "There is no valid FAT volume",
    "The f_mkfs() aborted due to any problem",
    "Could not get a grant to access the volume within defined period",
    "The operation is rejected according to the file sharing policy",
    "LFN working buffer could not be allocated",
    "Number of open files > FF_FS_LOCK",
    "Given parameter is invalid",
};


#define FF_CHECK(x, message, ...) { \
    fresult = x; \
    if (fresult != FR_OK) { \
        error_display( \
            message "\n" \
            " > FatFs error: %s\n" \
            " > SD card error: %s (%08X)", \
            __VA_ARGS__ __VA_OPT__(,) \
            fatfs_error_codes[fresult], \
            sc64_error_description(sc64_error_fatfs), sc64_error_fatfs \
        ); \
    } \
}


static void fix_menu_file_size (FIL *fil) {
    fil->obj.objsize = ALIGN(f_size(fil), FF_MAX_SS);
}


/* Read the complete menu through adjacent allocation extents. The temporary
   map is detached before return; fragmented maps that do not fit use FatFs. */
static FRESULT menu_read (FIL *file, UINT *bytes_read) {
    if (f_size(file) > 0x04000000) return FR_INVALID_PARAMETER;
    DWORD map[128];
    map[0] = sizeof(map) / sizeof(map[0]);
    file->cltbl = map;
    FRESULT result = f_lseek(file, CREATE_LINKMAP);
    file->cltbl = NULL;
    if (result == FR_NOT_ENOUGH_CORE) {
        return f_read(file, (void *)ROM_ADDRESS, f_size(file), bytes_read);
    }
    if (result != FR_OK) return result;
    uint32_t remaining = (f_size(file) + 511) / 512;
    uint32_t address = ROM_ADDRESS;
    FATFS *fs = file->obj.fs;
    for (unsigned i = 1; remaining && map[i]; i += 2) {
        uint64_t run = (uint64_t)map[i] * fs->csize;
        uint32_t count = run < remaining ? run : remaining;
        uint64_t sector = (uint64_t)fs->database + (uint64_t)(map[i + 1] - 2) * fs->csize;
        if (sector + count > 0x100000000ULL) return FR_INVALID_PARAMETER;
        sc64_error_fatfs = sc64_sd_read_sectors((void *)address, sector, count);
        if (sc64_error_fatfs != SC64_OK) return FR_DISK_ERR;
        address += count * 512;
        remaining -= count;
    }
    if (remaining) return FR_INT_ERR;
    *bytes_read = f_size(file);
    return FR_OK;
}

void menu_load (void) {
    sc64_error_t error;
    bool writeback_pending;
    FRESULT fresult;
    FATFS fs;
    FIL fil;
    UINT bytes_read;

    do {
        if ((error = sc64_writeback_pending(&writeback_pending)) != SC64_OK) {
            error_display("Command WRITEBACK_PENDING failed\n (%08X) - %s", error, sc64_error_description(error));
        }
    } while (writeback_pending);

    if ((error = sc64_writeback_disable()) != SC64_OK) {
        error_display("Could not disable save writeback\n (%08X) - %s", error, sc64_error_description(error));
    }

    FF_CHECK(f_mount(&fs, "", 1), "SD card initialize error");
    FF_CHECK(f_open(&fil, "sc64menu.n64", FA_READ), "Could not open menu executable (sc64menu.n64)");
    FF_CHECK(f_size(&fil) > 0x04000000 ? FR_INVALID_PARAMETER : FR_OK, "Menu exceeds SDRAM capacity");
    fix_menu_file_size(&fil);
    FF_CHECK(menu_read(&fil, &bytes_read), "Could not read menu file");
    FF_CHECK((bytes_read != f_size(&fil)) ? FR_INT_ERR : FR_OK, "Read size is different than expected");
    FF_CHECK(f_close(&fil), "Could not close menu file");
    FF_CHECK(f_unmount(""), "Could not unmount drive");
}
