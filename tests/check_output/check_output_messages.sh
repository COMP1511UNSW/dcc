#!/bin/bash
# the explanations given for particular kinds of incorrect output

cat >messages.c <<eof
#include <stdio.h>
#include <string.h>
int main(int argc, char *argv[]) {
    if (argc > 1 && strcmp(argv[1], "--zero-byte") == 0) {
        printf("a%cb\n", 0);
    } else if (argc > 1) {
        fputs(argv[1], stdout);
    }
    return 0;
}
eof
"$dcc" messages.c -o messages || exit 1

run_case() {
	echo "*** $1" 1>&2
	DCC_EXPECTED_STDOUT="$2" DCC_MAX_STDOUT_BYTES="$4" ./messages "$3" 2>&1 >/dev/null |
		grep -E 'Execution (stopped|failed) because|^Your program|missing|extra|non-printable|zero byte|infinite loop' 1>&2
}

run_case "extra characters at the end of the last line" $'Hello' $'Hello!' ""
run_case "missing last character"                       $'Hello!\n' $'Hello\n' ""
run_case "missing final newline"                        $'Hello\n' $'Hello' ""
run_case "non-printable character"                      $'ab\n' $'a\x10b\n' ""
run_case "zero byte"                                    $'ab\n' --zero-byte ""
run_case "too much output"                              $'Hello world\n' $'Hello world\n' 5
run_case "no output"                                    $'Hello\n' "" ""

rm -f messages.c messages
