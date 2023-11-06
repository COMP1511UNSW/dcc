#!/usr/bin/env bash
unset CDPATH
export PATH=/bin:/usr/bin:.

for var in $(env|egrep -v 'PATH|LOCALE|LC_|LANG'|grep '^[a-zA-Z0-9_]*='|cut -d= -f1)
do
	unset $var
done

export tests_dir="$(dirname $(readlink -f $0))"
export dcc="$(readlink -f ${1:-"./dcc"})"
export c_compiler="${2:-clang}"
export cpp_compiler="${3:-clang++}"

command -v "$dcc" > /dev/null || {
	echo "$0: error: $dcc not found"
	exit 1
}

e="$tests_dir/extracted_compile_time_errors"
mkdir -p "$e"
(
	cd "$e" || exit
	rm -f *.c
	python3 ../../compile_time_python/compiler_explanations.py --create_test_files
)

export clang_version=$($c_compiler -v 2>&1|sed 's/.* version *//;s/ .*//;1q'|cut -d. -f1,2)
export platform=$($c_compiler -v 2>&1|sed '1d;s/.* //;2q')
n_processes=$(($(getconf _NPROCESSORS_ONLN) / 2 + 1))
initial_run=$(
	{
		ls "$tests_dir"/run_time_errors/*.*
		ls "$tests_dir"/extracted_compile_time_errors/*.c
		ls "$tests_dir"/compile_time_errors/*.c
		ls "$tests_dir"/run_time_no_errors/*.*
		ls "$tests_dir"/check_output/*.sh
	}|
	grep -E '\.(sh|c|cpp)$'|
	shuf|
	xargs -P$n_processes -n1 "$tests_dir"/single_test.sh --quick|
	sort
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
	"$tests_dir"/single_test.sh "$src_file"
	test_result="$?"
	test "$test_result" = 0 && 
		continue
	test "$test_result" = 2 && 
		break
	tests_failed=$((tests_failed + 1))
done
echo $tests_failed tests failed
