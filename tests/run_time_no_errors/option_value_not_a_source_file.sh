#!/bin/sh
# the value of an option like -x is not a source file, even when a file of that
# name happens to exist.  dcc used to hand it to the check for a compiled
# program given as source, so -x c failed whenever there was a program called c

cat >option_value.c <<eof2
#include <stdio.h>
int main(void) {
    printf("compiled\n");
    return 0;
}
eof2

# a compiled program named c, which is what -x c would be mistaken for
"$dcc" option_value.c -o c || exit 1

"$dcc" -x c option_value.c -o option_value || exit 1
./option_value

mkdir -p option_value_include
echo '#define OPTION_VALUE 1' >option_value_include/option_value.h
cat >option_value_include_user.c <<eof2
#include "option_value.h"
#include <stdio.h>
int main(void) {
    printf("included %d\n", OPTION_VALUE);
    return 0;
}
eof2

"$dcc" --include-directory option_value_include option_value_include_user.c -o option_value_include_user || exit 1
./option_value_include_user

rm -fr c option_value.c option_value option_value_include option_value_include_user.c option_value_include_user
