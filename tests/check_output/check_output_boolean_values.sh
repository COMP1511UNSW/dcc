#!/bin/bash
# the DCC_* output-checking variables are true only when non-empty and
# not starting with 0, f, F, n or N, and \r\n in output or expected output
# is always treated as \n

cat >booleans.c <<eof2
#include <stdio.h>
int main(void) {
    printf("Hello World\n");
    return 0;
}
eof2
"$dcc" booleans.c -o booleans || exit 1

run_case() {
	echo "*** $1" 1>&2
	if DCC_EXPECTED_STDOUT="$2" env "${@:3}" ./booleans 2>&1 >/dev/null |
		grep -q 'Execution stopped because'
	then
		echo "output rejected" 1>&2
	else
		echo "output accepted" 1>&2
	fi
}

for value in 1 yes true Y T y t; do
	run_case "DCC_IGNORE_CASE=$value is true"  $'hello world\n' DCC_IGNORE_CASE="$value"
done
for value in 0 no false NO n N f F 0yes ""; do
	run_case "DCC_IGNORE_CASE='$value' is false" $'hello world\n' DCC_IGNORE_CASE="$value"
done
run_case "DCC_IGNORE_TRAILING_WHITE_SPACE defaults to true" $'Hello World   \n'
run_case "DCC_IGNORE_TRAILING_WHITE_SPACE=no"               $'Hello World   \n' DCC_IGNORE_TRAILING_WHITE_SPACE=no
run_case "expected output with \\r\\n line ending always accepted" $'Hello World\r\n' DCC_IGNORE_TRAILING_WHITE_SPACE=0
run_case "DCC_IGNORE_CHARACTERS overrides DCC_COMPARE_ONLY_CHARACTERS" $'H\n' DCC_COMPARE_ONLY_CHARACTERS=HW DCC_IGNORE_CHARACTERS=W
run_case "DCC_IGNORE_WHITE_SPACE overrides DCC_COMPARE_ONLY_CHARACTERS" $'HelloWorld\n' DCC_COMPARE_ONLY_CHARACTERS='Hello World' DCC_IGNORE_WHITE_SPACE=1
run_case "DCC_COMPARE_ONLY_CHARACTERS can not ignore newlines" 'Hello World' DCC_COMPARE_ONLY_CHARACTERS=HW

rm -f booleans.c booleans
