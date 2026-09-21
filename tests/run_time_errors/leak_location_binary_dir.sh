#!/bin/sh
# valgrind prints only the basename of a source file, so a leak allocated
# inside libc is located by looking for the student's file beside the binary
# as well as in the directory the program was run from

# so a failure is reported rather than hanging the tests
command -v timeout >/dev/null && limit="timeout -k 2 60"

cat >leak_location_binary.c <<'eof'
#include <stdlib.h>
#include <string.h>

int main(void) {
	char *s = strdup("leaked");
	return s == NULL;
}
eof

"$dcc" --leak-check -fsanitize=valgrind leak_location_binary.c -o leak_location_binary || exit 1

mkdir -p leak_location_elsewhere
cd leak_location_elsewhere || exit 1
$limit ../leak_location_binary
echo "exit status: $?" 1>&2
cd ..
rm -fr leak_location_binary.c leak_location_binary leak_location_elsewhere
