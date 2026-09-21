#!/bin/sh
# infinite recursion overflows the stack: dcc must explain it, with the
# location, in both the default and the single AddressSanitizer modes
# (the depth reached and the exact line vary, so only the stable lines are kept)

cat >infinite_recursion.c <<eof
#include <stdio.h>

int count(int n) {
    if (n < 0) {
        return 0;
    }
    return count(n + 1) + 1;
}

int main(int argc, char *argv[]) {
    printf("%d\n", count(argc));
    return 0;
}
eof

for flags in "" -fsanitize=address; do
	echo "*** dcc $flags" 1>&2
	# shellcheck disable=SC2086
	"$dcc" $flags infinite_recursion.c -o infinite_recursion || exit 1
	./infinite_recursion 2>&1 >/dev/null |
		grep -E 'stack overflow|infinite recursion|Execution stopped in|^count\(|^\.\.\.|^main' |
		sed 's/n=\(<unknown>\|[0-9]*\)/n=N/; s/ at line [0-9]*:/ at line N:/' |
		sort -u 1>&2
	echo "exit status non-zero: $(./infinite_recursion >/dev/null 2>&1 || echo yes)" 1>&2
done
rm -f infinite_recursion.c infinite_recursion
