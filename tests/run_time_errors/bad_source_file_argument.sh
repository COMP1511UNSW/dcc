#!/bin/sh
# dcc must not be stopped by an argument which is not an ordinary source file:
# a character device was read until memory ran out, a response file naming
# itself was expanded forever, and a NUL in a pathname escaped every handler

echo "*** character device" 1>&2
timeout 10 "$dcc" /dev/zero -o bad_source_file >/dev/null 2>&1
echo "exit status $?" 1>&2

echo "*** recursive response file" 1>&2
echo '@bad_source_file.rsp' >bad_source_file.rsp
timeout 10 "$dcc" @bad_source_file.rsp 2>&1 >/dev/null | sed 1q 1>&2

echo "*** null byte in response file" 1>&2
printf 'bad\0source.c\n' >bad_source_file_nul.rsp
timeout 10 "$dcc" @bad_source_file_nul.rsp 2>&1 >/dev/null | sed 1q 1>&2

# naming the same response file twice, or two response files which both name a
# third, is not recursion and must compile as it does for clang
cat >bad_source_file.c <<eof
int main(void) { return 0; }
eof
echo '-Wall' >bad_source_file_flags.rsp
echo '@bad_source_file_flags.rsp bad_source_file.c' >bad_source_file_a.rsp
echo '@bad_source_file_flags.rsp -lm' >bad_source_file_b.rsp

echo "*** same response file twice" 1>&2
timeout 10 "$dcc" @bad_source_file_flags.rsp bad_source_file.c @bad_source_file_flags.rsp -o bad_source_file
echo "exit status $?" 1>&2

echo "*** two response files naming a third" 1>&2
timeout 10 "$dcc" @bad_source_file_a.rsp @bad_source_file_b.rsp -o bad_source_file
echo "exit status $?" 1>&2

rm -f bad_source_file bad_source_file.c bad_source_file*.rsp
