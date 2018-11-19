#!/bin/bash
unset CDPATH

tests_dir=$(dirname $(readlink -f $0))
cd "$tests_dir"

trap 'rm -fr tmp.* a.out' EXIT INT TERM

# some values reported in errors are not determinate (e.g. variable addresses)
# and will vary between execution and definitely between platforms
# so delete them before diff-ing errors
REMOVE_NON_DETERMINATE_VALUES='
	s/^\([a-z].* = \).*/\1 <deleted-value>/g
	s/0x[0-9a-f]*/0x<deleted-hexadecimal-constant>/g
	s/-*[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]*/<deleted-large-integer-constant>/g
	s?/tmp/[^ ]*\.o??g
'

dcc="${1:-./dcc}"

mkdir -p extracted_compile_time_tests
cd extracted_compile_time_tests || exit
rm -f *.c
python3 ../../explain_compiler_output.py --create_test_files
cd ../..

test_failed=0
for src_file in tests/extracted_compile_time_tests/*.c tests/compile_time/*.c tests/run_time/*.c
do
	rm -f a.out
	expected_stderr_file="$tests_dir/expected_output/`basename $src_file .c`.stderr.txt"
	dcc_flags=
	eval `egrep '^//\w+=' "$src_file"|sed 's/..//'`
	"$dcc" $dcc_flags "$src_file" 2>tmp.actual_stderr >/dev/null
	test ! -s tmp.actual_stderr && ./a.out </dev/null   2>>tmp.actual_stderr >/dev/null
	
	if test ! -s tmp.actual_stderr
	then
		echo
		echo "Test dcc $dcc_flags $src_file failed - no error messages"
		test_failed=1
		continue
	fi 
	
	if test ! -e "$expected_stderr_file"
	then
		echo
		echo "'$expected_stderr_file' does not exist, creating with these contents:"
		echo
		cat tmp.actual_stderr
		sed "$REMOVE_NON_DETERMINATE_VALUES" tmp.actual_stderr >"$expected_stderr_file"
		echo
		echo "if above is not correct output for this test: rm '$expected_stderr_file' "
		continue
	fi 

	sed "$REMOVE_NON_DETERMINATE_VALUES" tmp.actual_stderr >tmp.corrected_stderr
	
	if diff -iBw "$expected_stderr_file" tmp.corrected_stderr >/dev/null
	then
		echo -n .
	else
		echo
		echo "Test dcc $dcc_flags  failed output different to expected - rm '$expected_stderr_file' if output is correct"
		echo Differences are:
		echo
		diff -iBw "$expected_stderr_file" tmp.corrected_stderr
		echo
		echo "if output is correct: rm '$expected_stderr_file'"
		test_failed=1
		continue
	fi
done
test $test_failed = 0 && echo && echo All tests passed
exit $test_failed
