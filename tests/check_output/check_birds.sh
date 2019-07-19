#!/bin/bash

dcc=${dcc:-./dcc}

bird_directory=$(dirname $(readlink -f "$0"))/birds

export DCC_EXPECTED_STDOUT="  ___
 ('v')
((___))
 ^   ^
"

for bird in "$bird_directory"/bird-*.c
do
	basename "$bird"
	$dcc "$bird"
	./a.out || continue
	echo "Test $bird failed" 
	exit 1
done
echo "All Tests Correct"
exit 0