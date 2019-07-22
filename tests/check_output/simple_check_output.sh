#!/bin/bash

dcc=${dcc:-./dcc}

cat >tmp.c <<eof
#include <stdio.h>
int main(int argc, char *argv[]) {printf("%s", argv[1]);return 0;}
eof

$dcc tmp.c || exit

export DCC_EXPECTED_STDOUT=$'Hello!\n'

function run_test {
	label="$1"
	environment_variables="$2"
	actual_output="$3"

	test_number=$((test_number + 1))

	(
		echo "*** Test $test_number - $label" 1>&2
		echo "*** Test Environment $environment_variables" 1>&2
		echo "expected output: $DCC_EXPECTED_STDOUT" 1>&2
		echo "actual output  : $actual_output" 1>&2
		
		eval "$environment_variables"' ./a.out "$actual_output" >/dev/null'
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

run_test default-1                        ""                                                $'Hello!\n'

run_test no-output-1-fail                 ""                                                $''

run_test trailing-white-space-1           ""                                                $'Hello!   \n'
run_test trailing-white-space-2-fail      "DCC_IGNORE_TRAILING_WHITE_SPACE=0"               $'Hello!   \n'

run_test extra-new-line-1-fail            ""                                                $'Hello!\n\n'
run_test extra-new-line-2                 "DCC_IGNORE_EMPTY_LINES=1"                        $'Hello!\n\n'

run_test missing-new-line-1-fail          ""                                                $'Hello!'

run_test ignore-case-1-fail               ""                                                $'hEllo!\n'
run_test ignore-case-2                    "DCC_IGNORE_CASE=1"                               $'hEllo!\n'

run_test ignore-white-space-1-fail               ""                                         $'H ello\t!\n'
run_test ignore-white-space-2            "DCC_IGNORE_WHITE_SPACE=1"                         $'H ello\t!\n'

run_test ignore-characters-1             "DCC_IGNORE_CHARACTERS=+"                          $'+++Hello!+++\n'
run_test ignore-characters-2-fail        "DCC_IGNORE_CHARACTERS=lzn"                        $'Hen\n'
run_test ignore-characters-3             "DCC_IGNORE_CHARACTERS=lzno!"                      $'Hen\n'
 
run_test compare-only-characters-1-fail "DCC_COMPARE_ONLY_CHARACTERS=Hel"                   $'HiheHilloHi\t!\n'
run_test compare-only-characters-2      "DCC_COMPARE_ONLY_CHARACTERS=el"                    $'HiheHilloHi\t!\n'
run_test compare-only-characters-3-fail "DCC_COMPARE_ONLY_CHARACTERS=hel"                   $'HiheHilloHi\t!\n'
run_test compare-only-characters-4      "DCC_IGNORE_CASE=1 DCC_COMPARE_ONLY_CHARACTERS=hel" $'Hell\n'


echo All Tests Correct 1>&2

