#!/bin/sh
# -fsyntax-only checks the program without producing an executable

cat >syntax_only.c <<eof
int main(void) {
    return 0;
}
eof

"$dcc" -fsyntax-only syntax_only.c || exit 1
test -e a.out && echo "a.out was produced" 1>&2
echo "syntax only ok"
rm -f syntax_only.c
