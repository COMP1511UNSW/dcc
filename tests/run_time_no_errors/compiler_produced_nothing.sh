#!/bin/sh
# dcc took the exit status of --c-compiler as proof a program had been built,
# so a compiler which quietly does nothing reported success and left whatever
# executable was there before in place

cat >compiler_produced_nothing.c <<'eof'
int main(void) {
	return 0;
}
eof

"$dcc" --c-compiler=/bin/true compiler_produced_nothing.c -o compiler_produced_nothing 2>error_output
test $? -eq 0 && echo "dcc reported success without compiling"
test -e compiler_produced_nothing && echo "a program was produced"
sed 's/^/dcc said: /' error_output

# -fsyntax-only and -E ask for no program, so they must not be reported as a
# compiler which produced nothing
"$dcc" -fsyntax-only compiler_produced_nothing.c -o syntax_only_program || exit 1
"$dcc" -E compiler_produced_nothing.c -o preprocessed_output >/dev/null || exit 1
# as do the options which make the compiler print information and exit,
# whose output dcc passes through, so it is discarded here
for probe in '-print-file-name=libm.a' '-dumpmachine' '-###'
do
	"$dcc" "$probe" compiler_produced_nothing.c -o probe_program >/dev/null 2>probe_error ||
		echo "dcc exited non-zero for $probe"
	grep -q 'did not produce' probe_error && echo "dcc complained about $probe"
done
echo "nothing asked for, nothing reported"

rm -f compiler_produced_nothing.c error_output syntax_only_program preprocessed_output
rm -f probe_program probe_error a.out
