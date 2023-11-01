#!/bin/bash

cat >exit_42.c <<eof
#include <stdlib.h>
int main(void) {exit(42);}
eof

cat >return_42.c <<eof
int main(void) {return 42;}
eof

for source in exit_42.c return_42.c
do
	$dcc "$source" || 
		continue
	./a.out
	exit_status=$?
	test "$exit_status" != 42 &&
		echo "$source incorrect exit status: $exit_status" 1>&2
done

rm -f a.out exit_42.c return_42.c