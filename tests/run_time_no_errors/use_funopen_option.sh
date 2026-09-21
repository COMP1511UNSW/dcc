#!/bin/sh
# --use-funopen needs libbsd on Linux: without it dcc used to report a missing
# system header as an internal error against a file the user can not see

cat >use_funopen_option.c <<eof
int main(void) { return 0; }
eof

"$dcc" --use-funopen use_funopen_option.c -o use_funopen_option 2>use_funopen_option.err
if test -s use_funopen_option.err
then
	grep -E -c 'Internal error|<stdin>' use_funopen_option.err
	sed 1q use_funopen_option.err
else
	echo "libbsd available, --use-funopen compiled"
fi

rm -f use_funopen_option.c use_funopen_option.err use_funopen_option
