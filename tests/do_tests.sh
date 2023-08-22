#!/usr/bin/env bash
unset CDPATH
export PATH=/bin:/usr/bin:.

for var in $(env|egrep -v 'PATH|LOCALE|LC_|LANG'|grep '^[a-zA-Z0-9_]*='|cut -d= -f1)
do
	unset $var
done

export tests_dir=$(dirname $(readlink -f $0))
cd "$tests_dir"
rm -f */a.out
export dcc="${1:-$(readlink -f ../dcc)}"
export dcc_cpp="${dcc}++"
export c_compiler="${2:-clang}"
export cpp_compiler="${3:-clang++}"

mkdir -p extracted_compile_time_errors
cd extracted_compile_time_errors || exit
rm -f *.c
python3 ../../compile_time_python/compiler_explanations.py --create_test_files
cd ..

export clang_version=$($c_compiler -v 2>&1|sed 's/.* version *//;s/ .*//;1q'|cut -d. -f1,2)
export platform=$($c_compiler -v 2>&1|sed '1d;s/.* //;2q')

n_cores=$(getconf _NPROCESSORS_ONLN)
initial_run=$(
	ls run_time_errors/*.* extracted_compile_time_errors/*.c compile_time_errors/*.c run_time_no_errors/*.* check_output/*.sh|
	xargs -P$(getconf _NPROCESSORS_ONLN) -n1 ./single_test.sh --quick
	)
	
echo "$initial_run"|grep '^Passed'|sort

second_run=$(
	echo "$initial_run"|
	grep -v '^Passed'|
	sed '
		s/ *#.*$//
		s/ *$//
		s/.* //
		'
	)
	
tests_failed=0
for src_file in $second_run
do
	./single_test.sh "$src_file"
	test_result="$?"
	test "$test_result" = 0 && 
		continue
	test "$test_result" = 2 && 
		break
	tests_failed=$((tests_failed + 1))
done
echo $tests_failed tests failed
