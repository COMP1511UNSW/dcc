#!/bin/sh
# a space or a colon in the pathname must not stop dcc naming the function
# the error occurred in, or printing its variables and the call traceback

cat >'assignment 1.c' <<eof
int deref(int *p) {
    return *p;
}

int main(void) {
    return deref(0);
}
eof
cp 'assignment 1.c' 'wei:rd.c'

"$dcc" 'assignment 1.c' -o space || exit 1
./space
"$dcc" 'wei:rd.c' -o colon || exit 1
./colon

rm -f 'assignment 1.c' 'wei:rd.c' space colon
