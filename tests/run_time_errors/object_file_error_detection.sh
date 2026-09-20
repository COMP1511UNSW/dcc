#!/bin/sh
# linking a .o file leaves dcc with AddressSanitizer alone, which must still
# detect memory errors, and dcc must say what that costs

cat >overflow.c <<eof
#include <stdio.h>
#include <string.h>
int main(void) {
    char name[4];
    strcpy(name, "hello world");
    printf("%s\n", name);
    return 0;
}
eof

"$dcc" -c overflow.c 2>/dev/null || exit 1
"$dcc" overflow.o -o overflow || exit 1
./overflow
rm -f overflow.c overflow.o overflow
