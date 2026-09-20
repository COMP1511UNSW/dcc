#!/bin/sh
# giving dcc a compiled program as a source file is the classic typo for -o
# and must be explained rather than producing linker errors

cat >compiled_hello.c <<eof
#include <stdio.h>
int main(void) {
    printf("hi\n");
    return 0;
}
eof

"$dcc" compiled_hello.c -o compiled_hello || exit 1
"$dcc" compiled_hello.c compiled_hello
rm -f compiled_hello.c compiled_hello
