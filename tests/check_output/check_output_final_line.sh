#!/bin/bash
# the final line of the expected output need not be newline terminated,
# and trailing white space is ignored there too

dcc=${dcc:-./dcc}

cat >tmp.c <<eof
#include <stdio.h>
int main(int argc, char *argv[]) {printf("%s", argv[1]);return 0;}
eof

$dcc tmp.c || exit

function run_test {
	label="$1"
	expected_output="$2"
	actual_output="$3"

	test_number=$((test_number + 1))

	(
		echo "*** Test $test_number - $label" 1>&2
		echo "expected output: $expected_output" 1>&2
		echo "actual output  : $actual_output" 1>&2

		DCC_EXPECTED_STDOUT="$expected_output" ./a.out "$actual_output" >/dev/null
		exit_status=$?

		case "$label" in
		*fail*) expected_result_status=1;;
		*) expected_result_status=0
		esac

		if (((exit_status != 0)  != $expected_result_status))
		then
			echo "*** Test failed ***" 1>&2
			exit 1
		fi
	) || exit 1
}

run_test unterminated-identical-1        '1 2 3'     '1 2 3'
run_test unterminated-identical-2        'a b'       'a b'
run_test unterminated-identical-3        'total: 7'  'total: 7'
run_test unterminated-last-byte-missing-fail  '1 2 3' '1 2'
run_test unterminated-trailing-space-1   'abc'       'abc   '
run_test unterminated-trailing-space-2   'a b'       'a b '
run_test unterminated-wrong-byte-fail    'abcd'      'abxd'
run_test partial-line-white-space        $'a\n'      $'a\n  '
run_test partial-line-extra-output-fail  $'a\n'      $'a\nb'
run_test white-space-only-unterminated-fail $'a\n'  '   '

echo All Tests Correct 1>&2
