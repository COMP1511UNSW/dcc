#!/bin/sh
# DCC_COLORIZE_OUTPUT colorizes compile-time and runtime messages
# even though stderr is not a terminal
# escape characters are shown as <ESC> so the expected output is readable

cat >colorized_compile.c <<eof2
int main(void) {
    return y;
}
eof2

cat >colorized_runtime.c <<eof2
int main(void) {
    int a[10] = {0};
    int i = 10;
    return a[i];
}
eof2

DCC_COLORIZE_OUTPUT=1 "$dcc" colorized_compile.c 2>&1 | sed "s/$(printf '\033')/<ESC>/g" 1>&2
"$dcc" colorized_runtime.c -o colorized_runtime || exit 1
DCC_COLORIZE_OUTPUT=1 ./colorized_runtime 2>&1 | sed "s/$(printf '\033')/<ESC>/g" 1>&2
echo "escapes without DCC_COLORIZE_OUTPUT: $(./colorized_runtime 2>&1 | grep -c "$(printf '\033')")" 1>&2
rm -f colorized_compile.c colorized_runtime.c colorized_runtime
