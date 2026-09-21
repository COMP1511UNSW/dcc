#!/bin/sh
# when the source file the error is in has been moved away dcc can not tell
# which function it was in, so it must not put another function's name on the
# line it reports

mkdir -p sub

cat >helper.c <<eof2
int deref(int *p) {
    return *p;
}
eof2

cat >sub/main.c <<eof2
int deref(int *p);

int main(void) {
    return deref(0);
}
eof2

cd sub || exit 1
# a pathname containing .. is not embedded in the executable
"$dcc" main.c ../helper.c -o missing_source || exit 1
rm ../helper.c
./missing_source 2>&1 | grep 'Execution stopped in' 1>&2
rm -f main.c missing_source
