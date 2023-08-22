#!/usr/bin/env bash

tmpdir=$(mktemp -d)
trap 'cd /;rm -fr "$tmpdir"' EXIT

quick=""
if test "$1" == --quick
then
	quick=1
	shift
fi
original_src_file="$1"

cp -p "$original_src_file" $tmpdir
src_file=$(basename "$1")
cd  $tmpdir
# some values reported in errors are not determinate (e.g. variable addresses)
# and will vary between execution and definitely between platforms
# so delete them before diff-ing errors
#
# also remove absolute pathnames
# so expected output is not filesystem location dependent
#
# and remove line/column numbers from error messages
# so minor changes to tests do not affect expected output


REMOVE_NON_DETERMINATE_VALUES='
	s/^\([a-z].* = \)[0-9][0-9]*$/\1 <integer>/g
	s/0x[0-9a-f]*/0x<deleted-hexadecimal-constant>/g
	s/-*[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]*/<deleted-large-integer-constant>/g
	s?/tmp/[^ ]*\.o??g
	s?^/.*:??
	s?^ *[0-9]* *|??
	s?^ *~*\^~* *$??
	s?clang-[0-9]*?clang?
	s?^\([^: ]*\):[0-9]*:[0-9]*:?\1?
	s? called at line [0-9]* of ? called at line ?
	s? at line [0-9]*:? at line:?
	s?: [0-9]* Killed?Killed?
	s?tests.*/??
'

# don't change the name of the variable src_file some  rely on it
compile_options_list=$(egrep '^//dcc_flags=' "$src_file"|sed 's?//??;s/ /#/g')
compile_options_list=${compile_options_list:-'dcc_flags=""'}

for compile_options in $compile_options_list
do
	rm -f a.out
	compile_options=$(echo "$compile_options"|sed 's/#/ /g')
	case "$src_file" in
	*.c)
		dcc_flags=
		suffix=`echo $compile_options|sed 's/^dcc_flags=//;s/ /_/g;s/["$]//g;s/src_file//;s?/?_?g'`
		eval $compile_options
		expected_output_basename="`basename $src_file .c`$suffix"
		#echo "$dcc" --c-compiler=$c_compiler $dcc_flags "$src_file"
		"$dcc" --c-compiler=$c_compiler $dcc_flags "$src_file" 2>tmp.actual_stderr >/dev/null
		test ! -s tmp.actual_stderr && DCC_DEBUG=1 ./a.out </dev/null   2>>tmp.actual_stderr >tmp.actual_stdout
		;;

	*.cpp)
		dcc_flags=
		suffix=`echo $compile_options|sed 's/^dcc_flags=//;s/ /_/g;s/["$]//g;s/src_file//;s?/?_?g'`
		eval $compile_options
		expected_output_basename="`basename $src_file`$suffix"
		#echo "$dcc" --c-compiler=$cpp_compiler $dcc_flags "$src_file"
		"$dcc_cpp" --c-compiler=$cpp_compiler $dcc_flags "$src_file" 2>tmp.actual_stderr >/dev/null
		test ! -s tmp.actual_stderr && DCC_DEBUG=1 ./a.out </dev/null   2>>tmp.actual_stderr >tmp.actual_stdout
		;;

	*.sh)
		expected_output_basename="`basename $src_file .sh`"
		$src_file </dev/null   2>tmp.actual_stderr >/dev/null
		;;
		
	*)
		echo Ignoring $src_file
		exit 0
	esac
	
	case "$original_src_file" in
	*no_error*)
		if test -s tmp.actual_stderr
		then
			echo FAILED: dcc $dcc_flags $original_src_file "# error messages"
			test -z "$quick" &&
				cat tmp.actual_stderr
			exit 1
		fi
		actual_output_file=tmp.actual_stdout
		;;
	*)
		if test ! -s tmp.actual_stderr
		then
			echo FAILED: dcc $dcc_flags $original_src_file "# no error messages"
			exit 1
		fi
		actual_output_file=tmp.actual_stderr
	esac
	sed -e "$REMOVE_NON_DETERMINATE_VALUES" $actual_output_file >tmp.corrected_output
	
	expected_output_dir="$tests_dir/expected_output/$expected_output_basename"
	mkdir -p "$expected_output_dir"
	expected_output_last_version=$(ls $expected_output_dir/*.txt 2>/dev/null|sed 1q)
	
	default_expected_output_dir="$tests_dir/expected_output/default"

	default_expected_output="$default_expected_output_dir/$expected_output_file"
	version_expected_output="$version_expected_output_dir/$expected_output_file"
	
	
	if test -z "$expected_output_last_version"
	then
		if test -n "$quick"
		then
			echo "NEW: $original_src_file "
			exit 0
		fi
		new_expected_output_file="$expected_output_dir/000000-clang-$clang_version-$platform.txt"
		echo
		echo "'$new_expected_output_file' does not exist, creating with these contents:"
		echo
		cat "$actual_output_file"
		cp  "$actual_output_file" "$new_expected_output_file"
		echo
		echo "if above is not correct output for this test: rm '$new_expected_output_file' "
		continue
	fi 

	# check if the output if we have matches any correct version
	passed=
	for expected_output_version in $expected_output_dir/*.txt
	do
		sed -e "$REMOVE_NON_DETERMINATE_VALUES" $expected_output_version >tmp.expected_output
		if diff -iBw tmp.expected_output tmp.corrected_output >/dev/null
		then
			echo Passed: dcc $dcc_flags $original_src_file
#				echo -n .
			passed=1
			break
		fi
	done
	test -n "$passed" && continue
	
	sed -e "$REMOVE_NON_DETERMINATE_VALUES" $expected_output_last_version >tmp.expected_output

	echo "FAILED: dcc $dcc_flags $original_src_file # error messages different to expected"
	test -n "$quick" &&
		exit 1
	echo Differences are:
	echo
	diff --color -u  -iBw tmp.expected_output tmp.corrected_output
	echo
	echo "Enter y to add this output to accepted versions."
	echo "Enter n to leave expected output versions unchanged."
	echo "Enter q to exit."
	
	echo -n "Action? "
	read response
	case "$response" in
	y*)
		last_version_number=$(basename $expected_output_last_version|cut -d- -f1)
		version_number=$(printf "%06d" $(($last_version_number + 1)))
		new_expected_output_file="$expected_output_dir/$version_number-clang-$clang_version-$platform.txt"
		cp -p "$actual_output_file" "$new_expected_output_file"
		;;
	q)
		exit 2
	esac
done
