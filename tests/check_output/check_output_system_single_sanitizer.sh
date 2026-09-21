#!/bin/sh
# the output of a command run with system() is the program's output too, and
# has to be checked in every mode - it used to be checked only when two
# sanitizers were running, so a correct program was failed with one

cat >system_output.c <<eof2
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    printf("a\n");
    system("echo b");
    return 0;
}
eof2

for sanitizer in "" "-fsanitize=address" "-fsanitize=valgrind"
do
	"$dcc" $sanitizer system_output.c -o system_output || exit 1

	echo "*** ${sanitizer:-default}, correct expected output"
	DCC_EXPECTED_STDOUT="$(printf 'a\nb\n')
" ./system_output

	echo "*** ${sanitizer:-default}, incorrect expected output"
	DCC_EXPECTED_STDOUT="$(printf 'a\nwrong\n')
" ./system_output
done

rm -f system_output.c system_output
