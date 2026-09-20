#!/bin/sh
# --leak-check with AddressSanitizer alone (no valgrind) uses LeakSanitizer,
# a different code path to the default valgrind leak checking

cat >leak.c <<eof2
#include <stdlib.h>
int main(void) {
    int *p = malloc(sizeof(int) * 10);
    p[0] = 1;
    p = NULL;
    return 0;
}
eof2

"$dcc" -fsanitize=address --leak-check leak.c -o leak || exit 1
./leak 2>leak.output
echo "exit status: $?" 1>&2
echo "leak reported: $(grep -c 'detected memory leaks' leak.output)" 1>&2
echo "leaked bytes: $(grep -o '[0-9]* byte(s) leaked' leak.output | sort -u)" 1>&2
rm -f leak.c leak leak.output
