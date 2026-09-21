#!/bin/bash
# a program which exceeds a (soft) CPU time limit gets SIGXCPU and
# dcc explains it and shows where the program was executing
# only the lines which do not depend on timing are kept

cat >cpu_time_limit.c <<eof2
#include <stdio.h>
int main(int argc, char *argv[]) {
    long count = 0;
    printf("starting\n");
    while (argc > 0) {
        count++;
        if (count < 0) {
            argc = 0;
        }
    }
    printf("finished %ld\n", count);
    return 0;
}
eof2

"$dcc" cpu_time_limit.c -o cpu_time_limit || exit 1
(
	ulimit -S -t 2
	./cpu_time_limit 2>&1 >/dev/null | grep -E 'CPU time limit|Execution stopped in' | sed 's/ at line.*//' 1>&2
)
rm -f cpu_time_limit.c cpu_time_limit
