#!/bin/sh
# dcc can not compile from stdin, and must say so for any spelling of stdin

cat >stdin_hello.c <<eof
#include <stdio.h>
int main(void) {
    printf("hi\n");
    return 0;
}
eof

for source in - /dev/stdin /dev/fd/0
do
	"$dcc" -x c -o stdin_hello "$source" <stdin_hello.c
done

# with stdin closed there is no file to look at, only the name
"$dcc" -x c -o stdin_hello /dev/stdin 0<&-

# a source file which is also redirected to stdin must still compile
"$dcc" -o stdin_hello stdin_hello.c <stdin_hello.c || exit 1
./stdin_hello
rm -f stdin_hello.c stdin_hello
