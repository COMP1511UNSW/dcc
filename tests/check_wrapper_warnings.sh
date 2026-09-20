#!/bin/sh
# Compile the C code dcc embeds in every program with -Wall -Wextra -Werror,
# for each combination of sanitizers, with clang and (if available) gcc.
#
# dcc compiles this code without warning options, but refuses to compile a
# program if the code produces any diagnostic at all, so a warning enabled by
# default in a new compiler version breaks every compilation.  Compiling with
# extra warnings enabled catches such problems early.

dcc=$(readlink -f "${1:-./dcc}")
temp_dir=$(mktemp -d) || exit 1
trap 'rm -fr "$temp_dir"' EXIT
cd "$temp_dir" || exit 1
ln -s "$dcc" dcc++

printf '#include <stdio.h>\nint main(void) { printf("hello\\n"); return 0; }\n' >hello.c
printf '#include <iostream>\nint main() { std::cout << "hello\\n"; }\n' >hello.cpp

status=0
n_compiled=0

# compile the generated wrapper files left by DCC_DEBUG=2 with extra warnings
# the commands recorded in tmp_dcc.sh give the flags each file is compiled with
# (a file may be compiled more than once with different flags)
check_wrappers() {
	for source in tmp_dcc_sanitizer*.c tmp_dcc_sanitizer*.cpp; do
		test -e "$source" || continue
		case "$source" in
		*.cpp) compilers=clang++; language=c++; object=dcc_cpp_wrapper_source.o;;
		*) compilers="clang gcc"; language=c; object=dcc_c_wrapper_source.o;;
		esac
		grep -- "-c $source " tmp_dcc.sh | sed "s/.*-o $object //" >compile_flags.txt
		if ! test -s compile_flags.txt; then
			echo "$0: no compile command for $source found in tmp_dcc.sh for: $1" 1>&2
			status=1
			continue
		fi
		while read -r compile_flags; do
			for compiler in $compilers; do
				command -v "$compiler" >/dev/null || continue
				# gcc does not have MemorySanitizer
				case "$compiler $compile_flags" in gcc*memory*) continue;; esac
				n_compiled=$((n_compiled + 1))
				# shellcheck disable=SC2086
				if ! "$compiler" -c -x "$language" "$source" -o /dev/null $compile_flags -Wall -Wextra -Werror; then
					echo "$0: $compiler warnings compiling $source for: $1" 1>&2
					status=1
				fi
			done
		done <compile_flags.txt
	done
}

for flags in "" -fsanitize=address -fsanitize=memory -fsanitize=valgrind -fsanitize=address,memory --leak-check --use-after-return; do
	rm -f tmp_dcc*
	# shellcheck disable=SC2086
	if ! DCC_DEBUG=2 "$dcc" $flags hello.c >dcc.out 2>&1; then
		# a sanitizer may not be available on this platform, e.g. MemorySanitizer
		# on 32-bit systems or valgrind on macOS, which is not a failure here
		if grep -qE 'not available|not supported|does not seem be installed' dcc.out; then
			echo "$0: skipping dcc $flags: $(sed 1q dcc.out)" 1>&2
			continue
		fi
		echo "$0: dcc $flags hello.c failed" 1>&2
		cat dcc.out 1>&2
		status=1
		continue
	fi
	check_wrappers "dcc $flags"
done

rm -f tmp_dcc*
if DCC_DEBUG=2 ./dcc++ hello.cpp >/dev/null 2>&1; then
	check_wrappers "dcc++"
else
	echo "$0: dcc++ hello.cpp failed" 1>&2
	status=1
fi

# guard against the check passing because nothing was found to compile
if test "$n_compiled" -lt 10; then
	echo "$0: only $n_compiled wrapper compilations were checked" 1>&2
	status=1
fi

test "$status" = 0 && echo "wrapper code compiles without warnings ($n_compiled compilations)"
exit "$status"
