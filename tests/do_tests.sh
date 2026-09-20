#!/usr/bin/env bash
unset CDPATH
export PATH=/bin:/usr/bin:.

for var in $(env|grep -E -v 'PATH|LOCALE|LC_|LANG'|grep '^[a-zA-Z0-9_]*='|cut -d= -f1)
do
	unset $var
done

tests_dir=$(dirname "$(readlink -f "$0")")
dcc=$(readlink -f "${1:-./dcc}")
export tests_dir dcc
export c_compiler="${2:-clang}"
export cpp_compiler="${3:-clang++}"

command -v "$dcc" > /dev/null || {
	echo "$0: error: $dcc not found"
	exit 1
}

# the fast unit tests of the Python code run first
python3 "$tests_dir/python_unit_tests.py" || exit 1

e="$tests_dir/extracted_compile_time_errors"
mkdir -p "$e"
(
	cd "$e" || exit
	rm -f *.c
	python3 ../../compile_time_python/compiler_explanations.py --create_test_files
)

clang_version=$($c_compiler -v 2>&1|sed 's/.* version *//;s/ .*//;1q'|cut -d. -f1,2)
platform=$($c_compiler -v 2>&1|sed '1d;s/.* //;2q')
export clang_version platform
# how many tests are run at once
#
# a test may run the program twice, once of them under valgrind, so this is
# half the processors by default.  Set DCC_TEST_JOBS to run fewer, for example
# on a machine with little memory or one shared with other work.
n_processes=${DCC_TEST_JOBS:-$(($(getconf _NPROCESSORS_ONLN) / 2 + 1))}
all_tests=$(
	{
		ls "$tests_dir"/run_time_errors/*.*
		ls "$tests_dir"/extracted_compile_time_errors/*.c
		ls "$tests_dir"/compile_time_errors/*.c
		ls "$tests_dir"/run_time_no_errors/*.*
		ls "$tests_dir"/check_output/*.sh
	}|
	grep -E '\.(sh|c|cpp)$'
	)

# the tests are first run in parallel, quietly
# xargs stops if a command is killed by a signal or exits with 255,
# so each test is run via sh so that xargs always sees a normal exit
initial_run=$(
	echo "$all_tests"|
	shuf|
	xargs -P$n_processes -n1 sh -c '"$0" --quick "$1" || true' "$tests_dir"/single_test.sh|
	sort
	)

echo "$initial_run"|grep '^Passed'|sort

# any test which produced no result at all is treated as failed
reported=$(echo "$initial_run"|sed 's/ *#.*$//; s/ *$//; s/.* //'|sort -u)
not_run=$(comm -23 <(echo "$all_tests"|sort -u) <(echo "$reported"))
for src_file in $not_run
do
	echo "NO RESULT: $src_file # re-running"
done

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
for src_file in $second_run $not_run
do
	"$tests_dir"/single_test.sh "$src_file"
	test_result="$?"
	test "$test_result" = 0 &&
		continue
	tests_failed=$((tests_failed + 1))
	test "$test_result" = 2 &&
		break
done
echo $tests_failed tests failed
test "$tests_failed" = 0
