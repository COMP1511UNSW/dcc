#!/bin/sh
# a real divergence between the two sanitizers must still be detected,
# now that a write of a different size on its own no longer counts as one

temp_dir=$(mktemp -d) || exit 1
trap 'rm -fr $temp_dir' EXIT

cat >$temp_dir/diverge.c <<eof
#include <stdio.h>
#include <stdlib.h>

int main(void) {
	// the sanitizers take different branches so they perform a different
	// number of writes, all of them the same size
	printf("a\n");
	printf("b\n");
	if (getenv("DCC_VALGRIND_RUNNING") == NULL) {
		printf("c\n");
	}
	return 0;
}
eof

# DCC_DEBUG when compiling puts dcc's own debugging output in the executable
DCC_DEBUG=1 "${dcc-dcc}" "$temp_dir/diverge.c" -o "$temp_dir/diverge" >/dev/null 2>&1 || exit 1
DCC_DEBUG=3 "$temp_dir/diverge" >/dev/null 2>$temp_dir/diverge.stderr
grep -c 'sanitizer synchronization lost' $temp_dir/diverge.stderr
