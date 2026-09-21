#!/bin/sh
# an executable whose pathname is not valid UTF-8, e.g. one copied from a
# Windows zip or made under a non-UTF-8 locale, must not stop valgrind's
# output being read: valgrind echoes the pathname before every error

# so a failure is reported rather than hanging the tests
command -v timeout >/dev/null && limit="timeout -k 2 60"

cat >non_utf8_path.c <<'eof'
#include <stdlib.h>
int main(void) {
	int *p = malloc(4 * sizeof *p);
	p[7] = 1;
	free(p);
	return 0;
}
eof

program=$(printf 'non_utf8_path\351')
"$dcc" -fsanitize=valgrind non_utf8_path.c -o "$program" || exit 1
$limit "./$program"
echo "exit status: $?" 1>&2
rm -f non_utf8_path.c "$program"
