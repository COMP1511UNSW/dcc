#!/bin/sh
# a shared library is linked, not a program the student meant to create with -o,
# whatever its name - libm.so.6 and libfoo.dylib are not source files either

cat >triple.c <<eof
int triple(int n) {
    return 3 * n;
}
eof

cat >shared_main.c <<eof
#include <stdio.h>
int triple(int n);
int main(void) {
    printf("%d\n", triple(14));
    return 0;
}
eof

"$c_compiler" -shared -fPIC -o libtriple.so.1 triple.c 2>/dev/null || exit 1
"$dcc" -o shared_main shared_main.c ./libtriple.so.1 || exit 1
echo "linked and ran: $(LD_LIBRARY_PATH=. ./shared_main)" >&2
rm -f triple.c libtriple.so.1 shared_main.c shared_main
