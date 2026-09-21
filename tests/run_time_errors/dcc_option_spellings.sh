#!/bin/sh
# the historical spellings of the explanation options must mean what they say,
# and naming only the undefined behaviour sanitizer must not be read as naming
# no sanitizer at all

# warns but still compiles, so the exit status below reports only whether the
# option itself was understood
cat >dcc_option_spellings.c <<eof
#include <stdio.h>
int main(void) { printf("%d\n", "x"); return 0; }
eof

for option in --explanations --explanation --no-explanations --no-explanation --no_explanation; do
	printf '%s explanations: ' "$option" 1>&2
	"$dcc" $option dcc_option_spellings.c -o dcc_option_spellings 2>dcc_option_spellings.err >/dev/null
	status=$?
	grep -c 'dcc explanation' dcc_option_spellings.err 1>&2
	# an unrecognised spelling reaches clang, which rejects it
	echo "$option exit status $status" 1>&2
done

cat >dcc_option_undefined.c <<eof
int main(void) { return 0; }
eof

printf -- '-fsanitize=undefined exit status ' 1>&2
"$dcc" -fsanitize=undefined dcc_option_undefined.c -o dcc_option_undefined >/dev/null 2>&1
echo "$?" 1>&2

"$dcc" -fsanitize=address,memory,valgrind dcc_option_undefined.c -o dcc_option_undefined 2>&1 >/dev/null |
	sed 1q 1>&2

rm -f dcc_option_spellings.c dcc_option_spellings.err dcc_option_undefined.c dcc_option_undefined
