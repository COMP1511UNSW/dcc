#!/bin/sh
# --no-explanations prints the compiler's messages without dcc's explanation

cat >no_explanations.c <<eof2
int main(void) {
    return y;
}
eof2

"$dcc" --no-explanations no_explanations.c
echo "exit status: $?" 1>&2
echo "explanation lines: $("$dcc" --no-explanations no_explanations.c 2>&1 | grep -c 'dcc explanation')" 1>&2
rm -f no_explanations.c
