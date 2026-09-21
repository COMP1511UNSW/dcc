#!/bin/sh
# a runtime error dcc can not finish explaining must still stop the program
# under valgrind, where it is waiting for the debugger which explains the
# error and so never exits by itself
#
# the one very long source line here defeats the code which explains it

# so a failure is reported rather than hanging the tests
command -v timeout >/dev/null && limit="timeout -k 2 60"

{
	echo '#include <stdio.h>'
	echo '#include <stdlib.h>'
	echo 'static int inner(int n) {'
	printf '    int v = 0;'
	i=0
	while [ "$i" -lt 700 ]; do
		printf ' v = v + %d;' "$i"
		i=$((i + 1))
	done
	echo
	echo '    int *p = malloc(4 * sizeof *p);'
	echo '    p[100] = v;'
	echo '    printf("%d ", p[100]);'
	echo '    free(p);'
	echo '    return n;'
	echo '}'
	echo 'static int outer(int n) { return inner(n); }'
	echo 'int main(int argc, char *argv[]) { return outer(argc) - 1; }'
} >long_line.c

"$dcc" -fsanitize=valgrind long_line.c -o long_line || exit 1
$limit ./long_line 2>long_line.stderr >/dev/null
status=$?
{
	test "$status" = 124 && echo "program did not terminate"
	# 141 is the status dcc exits with after an error it has reported
	echo "exit status: $status"
	echo "runtime error reported: $(grep -c '^Runtime error' long_line.stderr)"
	grep -E '^Execution stopped in' long_line.stderr | sed 's/ at line [0-9]*:/ at line N:/'
} 1>&2
rm -f long_line.c long_line long_line.stderr
