#!/bin/sh
# output a program writes to stderr before a runtime error must appear
# (and before the error, as stderr is unbuffered)

cat >stderr_before_error.c <<eof2
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char *argv[]) {
    int *p = malloc(3 * sizeof(int));
    fprintf(stderr, "a message on stderr\n");
    printf("a message on stdout\n");
    p[2] = 2;
    p[argc + 2] = 3;
    free(p);
    return 0;
}
eof2

"$dcc" stderr_before_error.c -o stderr_before_error || exit 1
./stderr_before_error 2>&1 >/dev/null | grep -v '^=*$' 1>&2
rm -f stderr_before_error.c stderr_before_error
