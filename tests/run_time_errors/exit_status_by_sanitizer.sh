#!/bin/sh
# every error dcc detects must stop the program with a non-zero exit status,
# in every combination of sanitizers, and without the shell reporting that the
# program was killed
#
# automarking decides from the exit status whether a program failed, so a zero
# status here marks a broken program as correct

cat >status_asan.c <<eof
#include <stdio.h>
int main(int argc, char *argv[]) {
    int a[4] = {0};
    a[argc + 3] = 1;
    printf("%d\n", a[0]);
    return 0;
}
eof

cat >status_uninitialized.c <<eof
#include <stdio.h>
int main(int argc, char *argv[]) {
    int a[2];
    a[0] = 0;
    if (a[argc] > 0) {
        printf("positive\n");
    }
    return 0;
}
eof

cat >status_leak.c <<eof
#include <stdlib.h>
int main(void) {
    int *p = malloc(40);
    p[0] = 1;
    return 0;
}
eof

cat >status_assert.c <<eof
#include <assert.h>
int main(int argc, char *argv[]) {
    assert(argc == 2);
    return 0;
}
eof

cat >status_correct.c <<eof
#include <stdlib.h>
int main(void) {
    exit(42);
}
eof

# report whether the program stopped with a failure status, and whether the
# shell printed a job-control message such as "Killed" that a student would see
run_program() {
	noise=$(bash -c "./$1 >/dev/null 2>/dev/null" 2>&1 | sed 1q)
	bash -c "./$1 >/dev/null 2>/dev/null" 2>/dev/null
	status=$?
	if test "$2" = expect_failure; then
		test "$status" = 0 && echo "  $1: not detected with these sanitizers" 1>&2 && return
		echo "  $1: stopped with a failure status" 1>&2
	else
		echo "  $1: exit status $status" 1>&2
	fi
	test -n "$noise" && echo "  $1: shell reported '$noise'" 1>&2
}

for flags in "" -fsanitize=address -fsanitize=valgrind -fsanitize=memory; do
	echo "*** dcc ${flags:-(default sanitizers)}" 1>&2
	for source in status_asan status_uninitialized status_assert status_correct; do
		# shellcheck disable=SC2086
		if ! "$dcc" $flags $source.c -o $source 2>/dev/null; then
			echo "  $source: not supported with these sanitizers" 1>&2
			continue
		fi
		case "$source" in
		status_correct) run_program $source expect_success;;
		*) run_program $source expect_failure
		esac
		rm -f $source
	done
	# shellcheck disable=SC2086
	if "$dcc" $flags --leak-check status_leak.c -o status_leak 2>/dev/null; then
		run_program status_leak expect_failure
		rm -f status_leak
	fi
done

rm -f status_asan.c status_uninitialized.c status_leak.c status_assert.c status_correct.c
