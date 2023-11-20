#!/bin/sh
temp_dir=$(mktemp -d /tmp/test_teaching_software.XXXXXXXXXX) || exit 1
trap 'rm -fr $temp_dir' EXIT

cat >$temp_dir/exit_42.c <<eof
#include <stdlib.h>
int main(void) {exit(42);}
eof

cat >$temp_dir/return_42.c <<eof
int main(void) {return 42;}
eof

for basename in exit_42 return_42
do
	"${dcc-dcc}" "$temp_dir/$basename.c" -o "$temp_dir/$basename"|| 
		continue
	"$temp_dir/$basename"
	exit_status=$?
	test "$exit_status" != 42 &&
		echo "$0: $source incorrect exit status: $exit_status" 1>&2
done
