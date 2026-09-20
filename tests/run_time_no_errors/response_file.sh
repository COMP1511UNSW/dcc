#!/bin/sh
# arguments in a @file are used once, with quoting, and not passed on to clang

cat >response_file.c <<eof
#include <stdio.h>
int main(void) {
    printf("%s\n", GREETING);
    return 0;
}
eof
printf '%s\n' '-Wextra "-DGREETING=\"hi there\""' 'response_file.c' >response_file.args

"$dcc" @response_file.args -o response_file || exit 1
./response_file
rm -f response_file.c response_file.args response_file
