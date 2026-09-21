#!/bin/sh
# a TMPDIR which can not be used made every compiler dcc runs fail, and dcc
# called that an internal error of its own.  The compilers are pointed at the
# temporary directory dcc has just created instead.

cat >bad_temporary_directory.c <<'eof'
#include <stdio.h>

int main(void) {
	printf("hello\n");
	return 0;
}
eof

touch not_a_directory
mkdir -p unwritable_directory
chmod 555 unwritable_directory

for bad_tmpdir in "$PWD/no_such_directory" "$PWD/not_a_directory" "$PWD/unwritable_directory"
do
	TMPDIR="$bad_tmpdir" "$dcc" bad_temporary_directory.c -o bad_temporary_directory || continue
	./bad_temporary_directory
done

chmod 755 unwritable_directory
rm -fr bad_temporary_directory.c bad_temporary_directory not_a_directory unwritable_directory
