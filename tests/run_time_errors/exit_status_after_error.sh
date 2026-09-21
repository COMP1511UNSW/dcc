#!/bin/sh
# a program stopped by a runtime error must exit with a non-zero status,
# whichever sanitizer detects the error and wherever in main it occurs
# (autotest tooling relies on the exit status)

cat >asan_error.c <<eof2
#include <stdio.h>
int main(int argc, char *argv[]) {
    int a[4] = {0};
    a[argc + 3] = 1;
    printf("%d\n", a[0]);
    return 0;
}
eof2

cat >valgrind_error_mid_main.c <<eof2
#include <stdio.h>
int main(int argc, char *argv[]) {
    int a[2];
    a[0] = 0;
    if (a[argc] > 0) {
        printf("positive\n");
    }
    printf("after\n");
    return 0;
}
eof2

cat >valgrind_error_last_statement.c <<eof2
#include <stdio.h>
int main(int argc, char *argv[]) {
    int a[2];
    a[0] = 0;
    if (a[argc] > 0) {
        printf("positive\n");
    }
}
eof2

cat >output_error.c <<eof2
#include <stdio.h>
int main(void) {
    printf("wrong output\n");
    return 0;
}
eof2

cat >assert_error.c <<eof2
#include <assert.h>
int main(int argc, char *argv[]) {
    assert(argc == 2);
    return 0;
}
eof2

for program in asan_error valgrind_error_mid_main valgrind_error_last_statement output_error assert_error; do
	"$dcc" $program.c -o $program || exit 1
	if test $program = output_error; then
		DCC_EXPECTED_STDOUT='right output
' ./$program >/dev/null 2>/dev/null
	else
		./$program >/dev/null 2>/dev/null
	fi
	status=$?
	if test $status = 0; then
		echo "$program: exit status zero" 1>&2
	else
		echo "$program: exit status non-zero" 1>&2
	fi
	rm -f $program.c $program
done
