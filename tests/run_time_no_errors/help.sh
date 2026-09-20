#!/bin/sh
# --help and --version print to stdout and exit successfully,
# also when they follow a source file (which is added to the embedded tar)

cat >help.c <<eof
int main(void) {
    return 0;
}
eof

"$dcc" --help | sed 1q || exit 1
"$dcc" help.c --help >/dev/null || exit 1
"$dcc" help.c --version | sed 's/ .*//'
rm -f help.c
