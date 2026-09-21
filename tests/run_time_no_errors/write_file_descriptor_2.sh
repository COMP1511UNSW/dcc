#!/bin/sh
# bytes written straight to file descriptor 2 must be written once,
# by the first sanitizer only

temp_dir=$(mktemp -d) || exit 1
trap 'rm -fr $temp_dir' EXIT

cat >"$temp_dir"/write_fd_2.c <<eof
#include <stdio.h>

// write is declared here because including unistd.h turns off the second
// sanitizer
extern long write(int fd, const void *buf, unsigned long n);

int main(void) {
	fprintf(stderr, "fprintf\n");
	write(2, "write\n", 6);
	return 0;
}
eof

"${dcc-dcc}" "$temp_dir/write_fd_2.c" -o "$temp_dir/write_fd_2" || exit 1
"$temp_dir/write_fd_2" 2>&1
