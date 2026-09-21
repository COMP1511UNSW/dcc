#!/bin/sh
# AddressSanitizer prints a line of 65 '=' characters before dcc intercepts
# its report, which was the first thing the student saw
#
# the programs are run without DCC_DEBUG, which deliberately leaves the
# sanitizer's own output visible

cat >banner.c <<eof
#include <stdlib.h>
int main(void) {
    int *p = malloc(sizeof *p);
    p[1] = 1;
    return 0;
}
eof

# an error before main is reported by the sanitizer itself, so the report
# stream has to have been redirected before the program's constructors run
cat >banner_before_main.c <<eof
static int *unmapped(void) {
    return (int *)0x10000000;
}

__attribute__((constructor)) static void initialize(void) {
    int *p = unmapped();
    *p = 1;
}

int main(void) {
    return 0;
}
eof

"$dcc" banner.c -o banner || exit 1
"$dcc" banner_before_main.c -o banner_before_main || exit 1
./banner 2>banner.out
./banner_before_main 2>banner_before_main.out
{
	echo "separator lines: $(grep -c '^=\{60,\}$' banner.out)"
	grep '^Runtime error' banner.out
	echo "separator lines before main: $(grep -c '^=\{60,\}$' banner_before_main.out)"
	grep '^Runtime error' banner_before_main.out
} >&2
rm -f banner.c banner banner.out
rm -f banner_before_main.c banner_before_main banner_before_main.out
