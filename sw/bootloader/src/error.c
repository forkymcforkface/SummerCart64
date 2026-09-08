#include <stdarg.h>
#include "display.h"
#include "init.h"
#include "version.h"


void error_display (const char *fmt, ...) {
    va_list args;

    deinit();

    display_init();

    version_print();
    display_printf("[ Runtime error ]\n");
    va_start(args, fmt);
    display_vprintf(fmt, args);
    va_end(args);
    display_printf("\n");

    while (true);
}
