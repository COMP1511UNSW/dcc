#!/bin/sh
# a command line too long for execve reached the student as a Python traceback
# from subprocess.py, which is exactly the kind of output dcc exists to replace

cat >argument_list_too_long.c <<'eof'
int main(void) {
	return 0;
}
eof

# one argument longer than MAX_ARG_STRLEN, via dcc's response file support
python3 -c "open('long.rsp', 'w').write('-DX=' + 'y' * 140000)" || exit 1

"$dcc" @long.rsp argument_list_too_long.c -o argument_list_too_long 2>error_output
test $? -eq 0 && echo "dcc reported success"
grep -q Traceback error_output && echo "dcc printed a Python traceback"
sed 's/^/dcc said: /' error_output

rm -f argument_list_too_long.c long.rsp error_output
