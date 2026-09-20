#!/bin/sh
# --embedded_environment_variable values are C string literals in the
# compiled program, so they must be escaped

cat >embedded_environment_variable.c <<eof
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    puts(getenv("DCC_TEST_VARIABLE"));
    return 0;
}
eof

"$dcc" '--embedded_environment_variable=DCC_TEST_VARIABLE=quote " backslash \ trigraph ??= equals = end' embedded_environment_variable.c -o embedded_environment_variable || exit 1
./embedded_environment_variable
rm -f embedded_environment_variable.c embedded_environment_variable
