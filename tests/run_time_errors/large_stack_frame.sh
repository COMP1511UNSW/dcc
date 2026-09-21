#!/bin/bash
# one oversized local array overflows the stack just as recursion does, but
# faults arbitrarily far past the stack limit: dcc must explain it in both the
# default and the single AddressSanitizer modes

cat >large_stack_frame.c <<eof
#include <stdio.h>

int main(int argc, char *argv[]) {
    int a[3000000];
    a[argc] = argc;
    printf("%d\n", a[argc]);
    return 0;
}
eof

for flags in "" -fsanitize=address; do
	echo "*** dcc $flags" 1>&2
	# shellcheck disable=SC2086
	"$dcc" $flags large_stack_frame.c -o large_stack_frame || exit 1
	(
		# the array must be larger than the stack
		ulimit -S -s 8192
		./large_stack_frame 2>&1 >/dev/null |
			grep -E 'stack overflow|infinite recursion|Execution stopped in' 1>&2
		echo "exit status non-zero: $(./large_stack_frame >/dev/null 2>&1 || echo yes)" 1>&2
	)
done
rm -f large_stack_frame.c large_stack_frame
