#!/bin/sh
# -o naming an existing source file would destroy a student's work
# the guard used to cover only .c and .h, so every C++ spelling was destroyed

for extension in c h cc cpp cxx c++ hpp
do
	printf 'int main(void) { return 0; }\n' >"keep.$extension"
	before=$(wc -c <"keep.$extension")
	"$dcc" keep.c -o "keep.$extension"
	after=$(wc -c <"keep.$extension")
	test "$before" = "$after" || echo "keep.$extension was overwritten" >&2
done

# a file which is not source is still a legitimate place to write a program
touch not_source.txt
"$dcc" keep.c -o not_source.txt || exit 1
./not_source.txt || exit 1
echo "wrote and ran not_source.txt" >&2

"$dcc" keep.c -o
echo "exit status non-zero: $(test $? -ne 0 && echo yes || echo no)" >&2

rm -f keep.* not_source.txt
