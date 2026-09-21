#!/bin/sh
# a source filename may begin with a space, which must not stop dcc
# recognizing the compiler's messages and explaining them

cat >' leading_space.c' <<'eof2'
int main(void) {
    return y;
}
eof2

"$dcc" ' leading_space.c' -o leading_space
rm -f ' leading_space.c'
