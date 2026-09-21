#!/bin/sh
# incremental compilation (-c then linking .o files) is supported with a warning

cat >tmp1.c <<eof
#include <stdio.h>
void f(void) {
    fprintf(stderr, "incremental compilation works\n");
}
eof

cat >tmp2.c <<eof
extern void f(void);
int main(void) {
    f();
    return 0;
}
eof

"$dcc" -c tmp1.c
"$dcc" -c tmp2.c
"$dcc" tmp1.o tmp2.o
./a.out
"$dcc" tmp1.o tmp2.c
./a.out
rm -f tmp1.c tmp2.c tmp1.o tmp2.o a.out
