#!/bin/bash

tests_dir=$(dirname $(readlink -f $0))
cd "$tests_dir"

trap 'rm -fr tmp.* a.out' EXIT INT TERM

# some values reported in errors are not determinate (e.g. variable addresses)
# and will vary between execution and definbitely between platforms
# so delete them before diff-ing errors
REMOVE_NON_DETERMINATE_VALUES='
	s/^\([a-z].* = \).*/\1 <deleted-value>/g
	s/0x[0-9a-f]*/0x<deleted-hexadecimal-constant>/g
	s/-*[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]*/<deleted-large-integer-constant>/g
'

dcc="${1:-../dcc}"

mkdir -p expected_output
test_failed=0
for src_file in *.c
do
	expected_stderr_file=expected_output/"`basename $src_file .c`.stderr.txt"
	dcc_flags=
	eval `egrep '^//\w+=' "$src_file"|sed 's/..//'`
	"$dcc" $dcc_flags "$src_file" 2>tmp.actual_stderr >/dev/null &&
	a.out 2>>tmp.actual_stderr >/dev/null && {
		echo "Test dcc $dcc_flags $src_file failed - zero exit status"
		test_failed=1
		continue
	} 
	
	if test ! -e "$expected_stderr_file"
	then
		echo "'$expected_stderr_file' does not exist, creating with these contents:"
		echo
		cat tmp.actual_stderr
		sed "$REMOVE_NON_DETERMINATE_VALUES" tmp.actual_stderr >"$expected_stderr_file"
		echo
		echo "if above is not correct output for this test: rm '$expected_stderr_file' "
		continue
	fi 

	sed "$REMOVE_NON_DETERMINATE_VALUES" tmp.actual_stderr >tmp.corrected_stderr
	
	diff -iBw "$expected_stderr_file" tmp.corrected_stderr >/dev/null || {
		echo "Test dcc $dcc_flags  failed output different to expected - rm '$expected_stderr_file' if output is correct"
		echo Differences are:
		echo
		diff -iBw "$expected_stderr_file" tmp.corrected_stderr
		echo
		echo "if output is correct: rm '$expected_stderr_file'"
		test_failed=1
		continue
	}
done
test $test_failed = 0 && echo All tests passed
exit $test_failed