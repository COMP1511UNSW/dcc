#!/bin/bash
# with too few file descriptors dcc can not start the second sanitizer, and
# whichever step fails first it must not signal pid 0, which is every process
# in the group, i.e. the shell running this script
#
# the whole range is covered because each limit fails at a different step -
# the pipes, the temporary file, writing it - and because one more or one
# fewer descriptor held by dcc moves the program from one step to the next

cat >low_file_descriptor_limit.c <<eof
#include <stdio.h>
int main(void) {
    printf("hello\n");
    return 0;
}
eof

"$dcc" low_file_descriptor_limit.c -o low_file_descriptor_limit || exit 1
for limit in 4 5 6 7 8 9 10 11 12
do
	# what the program manages to do varies with the limit, but the shell
	# which ran it must always still be here afterwards
	# the subshell's own stderr is redirected too: at some limits the
	# program is killed by the resource limit and the shell reports that,
	# which is not what is being tested here
	(ulimit -n $limit; ./low_file_descriptor_limit >/dev/null 2>/dev/null) 2>/dev/null
	echo "file descriptor limit $limit: still here"
done
./low_file_descriptor_limit
echo "exit status $?"
rm -f low_file_descriptor_limit.c low_file_descriptor_limit
