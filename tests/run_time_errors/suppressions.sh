#!/bin/sh
# --suppressions=<file> is passed to valgrind: a leak it suppresses is not reported

cat >leak.c <<eof2
#include <stdlib.h>
int main(void) {
    int *p = malloc(sizeof(int) * 10);
    p[0] = 1;
    p = NULL;
    return 0;
}
eof2

cat >leak.supp <<eof2
{
   ignore_malloc_in_main
   Memcheck:Leak
   match-leak-kinds: definite
   fun:malloc
   fun:main
}
eof2

echo "without suppressions:" 1>&2
"$dcc" --leak-check leak.c -o leak || exit 1
./leak
echo "with suppressions:" 1>&2
"$dcc" --leak-check --suppressions=leak.supp leak.c -o leak_suppressed || exit 1
./leak_suppressed
echo "done" 1>&2
rm -f leak.c leak.supp leak leak_suppressed
