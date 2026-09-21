#!/bin/bash
# output written by a process the program fork()s is part of its output,
# so the check has to see it too

dcc=${dcc:-./dcc}

cat >tmp.c <<eof
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>
int main(int argc, char *argv[]) {
	pid_t pid = fork();
	if (pid == 0) {
		printf("a\n");
		fflush(stdout);
		// a child leaving via exit() runs the at-exit handlers, which must
		// not check for output the parent has not printed yet
		if (argc > 1) {
			exit(0);
		}
		_exit(0);
	}
	waitpid(pid, NULL, 0);
	printf("b\n");
	return 0;
}
eof

$dcc tmp.c || exit

echo "*** Test 1 - output of child and parent together is correct" 1>&2
DCC_EXPECTED_STDOUT=$'a\nb\n' ./a.out >/dev/null ||
	{ echo "*** Test failed ***" 1>&2; exit 1; }

echo "*** Test 2 - a child which exits normally does not check output itself" 1>&2
DCC_EXPECTED_STDOUT=$'a\nb\n' ./a.out normal-exit >/dev/null ||
	{ echo "*** Test failed ***" 1>&2; exit 1; }

echo "*** Test 3 - incorrect parent output is still detected" 1>&2
DCC_EXPECTED_STDOUT=$'a\nc\n' ./a.out >/dev/null &&
	{ echo "*** Test failed ***" 1>&2; exit 1; }

echo All Tests Correct 1>&2
