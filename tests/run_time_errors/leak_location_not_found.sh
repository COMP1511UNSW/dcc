#!/bin/sh
# the reported leak location must not depend on the directory the program is
# run from: valgrind prints only a basename, so when dcc can find none of the
# frames' source files it must still report the frame which called malloc

# so a failure is reported rather than hanging the tests
command -v timeout >/dev/null && limit="timeout -k 2 60"

mkdir -p leak_location_src leak_location_run

cat >leak_location_src/leak_location.c <<'eof'
#include <stdlib.h>

static int *make_array(int n) {
	return malloc(n * sizeof(int));
}

int main(void) {
	int *p = make_array(10);
	p[0] = 1;
	return 0;
}
eof

"$dcc" --leak-check leak_location_src/leak_location.c -o leak_location_run/leak_location || exit 1

# neither the source directory nor anything else holding leak_location.c
cd leak_location_run || exit 1
$limit ./leak_location
echo "exit status: $?" 1>&2
cd ..
rm -fr leak_location_src leak_location_run
