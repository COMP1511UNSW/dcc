#!/bin/sh
# stdin larger than the pipe buffer is passed to the second sanitizer
# without losing synchronization, so the uninitialized variable is detected

cat >large_stdin.c <<eof
#include <stdio.h>
int main(void) {
    char line[256];
    long n_lines = 0;
    while (fgets(line, sizeof line, stdin) != NULL) {
        n_lines++;
    }
    int x;
    printf("%ld lines\n", n_lines);
    if (x > 0) {
        printf("positive\n");
    }
    return 0;
}
eof

"$dcc" large_stdin.c -o large_stdin || exit 1
awk 'BEGIN { for (i = 0; i < 5000; i++) print "line number", i, "with some padding text to make it longer" }' >large_stdin.txt
./large_stdin <large_stdin.txt
rm -f large_stdin.c large_stdin large_stdin.txt
