#!/bin/sh
temp_dir=$(mktemp -d /tmp/test_teaching_software.XXXXXXXXXX) || exit 1
trap 'rm -fr $temp_dir' EXIT

cat >$temp_dir/print_path.c <<eof
#include <stdlib.h>
#include <stdio.h>
int main(void) {
	puts(getenv("PATH"));
}
eof

"${dcc-dcc}" $temp_dir/print_path.c -o $temp_dir/print_path|| 
		continue
		
test_path="hello_dcc"
stdout=$(PATH="$test_path" $temp_dir/print_path)

test "$stdout" = "$test_path" &&
	exit 0
	
echo "$0: $source incorrect PATH '$stdout' versus '$test_path'" 1>&2
exit 1
