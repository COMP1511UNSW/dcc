#!/bin/bash
unset CDPATH

tests_dir=$(dirname $(readlink -f $0))
cd "$tests_dir"

trap 'exit_status=$?;rm -fr tmp* a.out;exit $exit_status' EXIT INT TERM

# some values reported in errors are not determinate (e.g. variable addresses)
# and will vary between execution and definitely between platforms
# so delete them before diff-ing errors
# also remove absolute pathnames so expected output is not filesystem location dependent
REMOVE_NON_DETERMINATE_VALUES='
	s/^\([a-z].* = \).*/\1 <deleted-value>/g
	s/0x[0-9a-f]*/0x<deleted-hexadecimal-constant>/g
	s/-*[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]*/<deleted-large-integer-constant>/g
	s?/tmp/[^ ]*\.o??g
	s?^/.*:??
'

export dcc="${1:-./dcc}"
c_compiler="${2:-clang}"

mkdir -p extracted_compile_time_errors
cd extracted_compile_time_errors || exit
rm -f *.c
python3 ../../compiler_explanations.py --create_test_files
cd ../..

clang_version=$($c_compiler -v 2>&1|sed 's/.* version *//;s/ .*//;1q'|cut -d. -f1,2)
platform=$($c_compiler -v 2>&1|sed '1d;s/.* //;2q')

expected_output_dir="$tests_dir/expected_output/clang-$clang_version-$platform"
mkdir -p $expected_output_dir
test_failed=0

for src_file in tests/extracted_compile_time_errors/*.c tests/compile_time_errors/*.c tests/run_time_errors/*.* tests/run_time_no_errors/*.*
do
	# don't change the name of the variable src_file some tests rely on it
	compile_options_list=$(egrep '^//dcc_flags=' "$src_file"|sed 's?//??;s/ /#/g')
	compile_options_list=${compile_options_list:-'dcc_flags=""'}

	for compile_options in $compile_options_list
	do
		rm -f a.out
		compile_options=$(echo "$compile_options"|sed 's/#/ /g')
		case "$src_file" in
		*.c)
			dcc_flags=
			suffix=`echo $compile_options|sed 's/^dcc_flags=//;s/ /_/g;s/["$]//g;s/src_file//'`
			eval $compile_options
			expected_output_file="$expected_output_dir/`basename $src_file .c`$suffix.txt"
			#echo "$dcc" --c-compiler=$c_compiler $dcc_flags "$src_file"
			"$dcc" --c-compiler=$c_compiler $dcc_flags "$src_file" 2>tmp.actual_stderr >/dev/null
			test ! -s tmp.actual_stderr && DCC_DEBUG=1 ./a.out </dev/null   2>>tmp.actual_stderr >tmp.actual_stdout
			;;

		*.sh)
			expected_output_file="$expected_output_dir/`basename $src_file .sh`.txt"
			$src_file </dev/null   2>tmp.actual_stderr >/dev/null
			;;
			
		*)
			echo Ignoring $src_file
			continue
		esac
		
		case "$src_file" in
		*no_error*)
			if test -s tmp.actual_stderr
			then
				echo
				echo "Test dcc $dcc_flags $src_file failed - error messages"
				cat tmp.actual_stderr
				test_failed=1
				continue
			fi
			actual_output_file=tmp.actual_stdout
			;;
		*)
			if test ! -s tmp.actual_stderr
			then
				echo
				echo "Test dcc $dcc_flags $src_file failed - no error messages"
				test_failed=1
				continue
			fi
			actual_output_file=tmp.actual_stderr
		esac
		
		if test ! -e "$expected_output_file"
		then
			echo
			echo "'$expected_output_file' does not exist, creating with these contents:"
			echo
			cat "$actual_output_file"
			sed "$REMOVE_NON_DETERMINATE_VALUES" $actual_output_file >"$expected_output_file"
			echo
			echo "if above is not correct output for this test: rm '$expected_output_file' "
			continue
		fi 
	
		sed -e "$REMOVE_NON_DETERMINATE_VALUES"  $actual_output_file >tmp.corrected_output
		if diff -iBw "$expected_output_file" tmp.corrected_output >/dev/null
		then
			echo -n .
		else
			echo
			echo "Test dcc $dcc_flags  failed output different to expected - rm '$expected_output_file' if output is correct"
			echo Differences are:
			echo
			diff -u  -iBw "$expected_output_file" tmp.corrected_output
			echo
			echo "if output is correct: rm '$expected_output_file'"
			test_failed=1
			continue
		fi
	done
done
test $test_failed = 0 && echo && echo All tests passed
exit $test_failed
