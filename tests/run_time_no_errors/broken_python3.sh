#!/bin/sh
# a python3 in PATH which can not be run must not stop the program running,
# nor stop its errors being explained: valgrind waits for the watcher dcc
# starts with python3, so if it never starts the program says nothing at all

mkdir -p fake_bin
cat >fake_bin/python3 <<'eof'
#!/bin/sh
exit 127
eof
chmod 755 fake_bin/python3
broken_path="$(pwd)/fake_bin:$PATH"

# so a failure is reported rather than hanging the tests
command -v timeout >/dev/null && limit="timeout 60"

cat >broken_python3.c <<'eof'
#include <stdio.h>
int main(void) {
	printf("hello\n");
	return 0;
}
eof

# dcc itself is run by python3, so only the program gets the broken PATH
"$dcc" broken_python3.c -o broken_python3 || exit 1
PATH="$broken_path" $limit ./broken_python3 || exit 1

# malloc so the uninitialized value is not found at compile time
cat >broken_python3_error.c <<'eof'
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char *argv[]) {
	int *a = malloc(4 * sizeof *a);
	a[0] = argc;
	if (a[argc]) {
		printf("uninitialized\n");
	}
	return 0;
}
eof

"$dcc" --valgrind broken_python3_error.c -o broken_python3_error || exit 1
PATH="$broken_path" $limit ./broken_python3_error >/dev/null 2>error_output
grep -q "^Runtime error: uninitialized variable accessed" error_output &&
	echo explained
