#!/bin/bash
# an expected output line longer than dcc can compare has to be reported
# as such, not as the program producing no output

dcc=${dcc:-./dcc}

cat >tmp.c <<eof
#include <stdio.h>
int main(void) {printf("x\n");return 0;}
eof

$dcc tmp.c || exit

expected_output=$(python3 -c "print('a' * 65536)")$'\n'

echo "*** Test 1 - expected line too long" 1>&2
DCC_EXPECTED_STDOUT="$expected_output" ./a.out >/dev/null &&
	{ echo "*** Test failed ***" 1>&2; exit 1; }

echo All Tests Correct 1>&2
