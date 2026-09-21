#!/bin/sh
# -O is for the gcc checking pass only: with --c-compiler=gcc it reached the
# student's program, where the optimizer deleted the error the sanitizers
# were meant to find

# the harness treats no output at all as a failure, so say why instead
command -v gcc >/dev/null || { echo "gcc not installed" 1>&2; exit 0; }

cat >gcc_compiler_option.c <<eof
#include <stdlib.h>
int main(void) { int *p = malloc(sizeof *p); free(p); free(p); return 0; }
eof

"$dcc" --c-compiler=gcc gcc_compiler_option.c -o gcc_compiler_option 2>/dev/null || exit 1
if ./gcc_compiler_option >/dev/null 2>&1
then
	echo "double free not detected" 1>&2
else
	echo "double free detected" 1>&2
fi

rm -f gcc_compiler_option.c gcc_compiler_option
