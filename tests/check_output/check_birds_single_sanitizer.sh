#!/bin/bash
# output checking with a single sanitizer:
# the check that all expected output was produced happens at exit,
# which is a different code path to the dual sanitizer case

export DCC_EXPECTED_STDOUT="  ___
 ('v')
((___))
 ^   ^
"

for sanitizer in address memory; do
	for bird in birds/bird-*.c; do
		echo "$sanitizer $(basename "$bird")" 1>&2
		"$dcc" -fsanitize=$sanitizer "$bird" || continue
		./a.out >/dev/null || continue
		echo "Test $bird failed" 1>&2
		exit 1
	done
	"$dcc" -fsanitize=$sanitizer birds/bird.c || exit 1
	./a.out >/dev/null || { echo "correct output rejected" 1>&2; exit 1; }
done
echo "All Tests Correct" 1>&2
exit 0
