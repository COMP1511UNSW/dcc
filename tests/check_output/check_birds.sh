#!/bin/bash

dcc=${dcc:-./dcc}

bird_directory=$tests_dir/check_output/birds

export DCC_EXPECTED_STDOUT="  ___
 ('v')
((___))
 ^   ^
"

for bird in "$bird_directory"/bird-*.c
do
	basename "$bird" 1>&2
	$dcc "$bird"
	./a.out >/dev/null || continue
	echo "Test $bird failed" 1>&2
	exit 1
done
echo "All Tests Correct" 1>&2
exit 0