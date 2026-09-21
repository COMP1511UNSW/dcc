#!/bin/sh
# a program which has written a partial line when an error stops it must
# still get an explanation, and its output must not be written twice
#
# the error report is produced from the signal handler, on a small alternate
# stack, and while the stdout write callback may still be running, so
# anything done with the program's streams there is easy to get wrong

cat >partial_signal.c <<eof
#include <stdio.h>
#include <signal.h>
int main(void) {
    printf("a partial line");
    raise(SIGSEGV);
    return 0;
}
eof

cat >partial_recursion.c <<eof
#include <stdio.h>
int count(int n) {
    if (n < 0) {
        return 0;
    }
    return count(n + 1) + 1;
}
int main(int argc, char *argv[]) {
    printf("a partial line");
    printf("%d\n", count(argc));
    return 0;
}
eof

cat >partial_output_check.c <<eof
#include <stdio.h>
int main(void) {
    printf("line1\n");
    printf("wrong\n");
    return 0;
}
eof

for source in partial_signal partial_recursion; do
	"$dcc" "$source.c" -o "$source" || exit 1
	echo "*** $source" 1>&2
	"./$source" 2>&1 >/dev/null | grep -E "Execution stopped (by|because)" 1>&2
	"./$source" >/dev/null 2>&1
	test $? = 0 && echo "$source: exit status zero" 1>&2
	echo "$source: explained and stopped" 1>&2
	rm -f "$source.c" "$source"
done

"$dcc" partial_output_check.c -o partial_output_check || exit 1
echo "*** partial_output_check" 1>&2
echo "each line of output printed once:" 1>&2
DCC_EXPECTED_STDOUT="line1
line2
" ./partial_output_check 2>/dev/null | sort | uniq -c | sed "s/^ *//" 1>&2
rm -f partial_output_check.c partial_output_check
