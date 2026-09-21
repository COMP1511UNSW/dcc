#!/bin/sh
# with --c-compiler=gcc the sanitizer report interception was compiled out, so
# every runtime error collapsed to one generic message.  gcc's libubsan exports
# the same hooks clang's does, so the error is reported as precisely

command -v gcc >/dev/null || exit 0

cat >gcc_sanitizer_report.c <<eof2
#include <stdio.h>
int main(void) {
    int a[3];
    a[0] = 0;
    int i = 5;
    printf("%d\n", a[i]);
    return 0;
}
eof2

cat >gcc_sanitizer_overflow.c <<eof2
#include <stdio.h>
int main(void) {
    int x = 2147483647;
    printf("%d\n", x + 1);
    return 0;
}
eof2

"$dcc" --c-compiler=gcc gcc_sanitizer_report.c -o gcc_sanitizer_report || exit 1
./gcc_sanitizer_report

"$dcc" --c-compiler=gcc gcc_sanitizer_overflow.c -o gcc_sanitizer_overflow || exit 1
./gcc_sanitizer_overflow

rm -f gcc_sanitizer_report.c gcc_sanitizer_report
rm -f gcc_sanitizer_overflow.c gcc_sanitizer_overflow
