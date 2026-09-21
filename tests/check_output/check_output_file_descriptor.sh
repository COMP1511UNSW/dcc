#!/bin/bash
# bytes the program puts on file descriptor 1 are its output too,
# whether or not they went through the stdout stream

dcc=${dcc:-./dcc}

cat >writefd.c <<eof
#include <unistd.h>
int main(void) {
    write(1, "a\n", 2);
    return 0;
}
eof
"$dcc" writefd.c -o writefd || exit 1

cat >mixed.c <<eof
#include <stdio.h>
#include <unistd.h>
int main(void) {
    printf("a\n");
    fflush(stdout);
    write(1, "b\n", 2);
    printf("c\n");
    return 0;
}
eof
"$dcc" mixed.c -o mixed || exit 1

cat >child.c <<eof
#include <stdlib.h>
int main(void) {
    system("echo a");
    return 0;
}
eof
"$dcc" child.c -o child || exit 1

cat >prompt.c <<eof
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    printf("Enter a number: ");
    system("echo 42");
    return 0;
}
eof
"$dcc" prompt.c -o prompt || exit 1

cat >partial.c <<eof
#include <stdio.h>
#include <unistd.h>
int main(void) {
    printf("a");
    write(1, "b\n", 2);
    return 0;
}
eof
"$dcc" partial.c -o partial || exit 1

# the timeout is here because output still buffered when a child process is
# started once deadlocked the two sanitizers, which would hang the test suite
run_case() {
	echo "*** $1" 1>&2
	DCC_EXPECTED_STDOUT="$3" timeout -k 2 20 "./$2" >tmp.stdout 2>tmp.stderr
	echo "exit status $?" 1>&2
	echo "printed '$(cat tmp.stdout)'" 1>&2
	grep -E -A1 'Execution (stopped|failed) because|^Your program|^The correct output line' tmp.stderr | grep -v '^--$' 1>&2
}

run_case "write to file descriptor 1"              writefd $'a\n'
run_case "write mixed with printf"                 mixed   $'a\nb\nc\n'
run_case "wrong line written to file descriptor 1" mixed   $'a\nX\nc\n'
run_case "output of a child process"               child   $'a\n'
run_case "child process started mid-line"          prompt  $'Enter a number: 42\n'
run_case "write to file descriptor 1 mid-line"     partial $'ab\n'

rm -f writefd.c writefd mixed.c mixed child.c child prompt.c prompt partial.c partial tmp.stdout tmp.stderr
