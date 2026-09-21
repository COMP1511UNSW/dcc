#!/bin/sh
# a DCC_DEBUG value which is not an integer is treated as 0, not a crash

cat >debug_level.c <<eof
int main(void) {
    return 0;
}
eof

DCC_DEBUG=x "$dcc" debug_level.c -o debug_level || exit 1
DCC_DEBUG=x ./debug_level && echo ok
rm -f debug_level.c debug_level
