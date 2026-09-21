#!/bin/bash
# the stack overflow heuristic must not claim a fault which is not one: a
# NULL dereference after a huge frame, and a wild pointer in a thread whose
# stack is nowhere near the main thread's

cat >not_stack_overflow_null.c <<eof
#include <stdio.h>

int main(int argc, char *argv[]) {
    char big[6 * 1024 * 1024];
    int *p = NULL;
    big[argc] = argc;
    *p = big[argc];
    printf("%d\n", *p);
    return 0;
}
eof

cat >not_stack_overflow_thread.c <<eof
#include <pthread.h>
#include <stdio.h>

void *wild(void *argument) {
    int local = 0;
    int *p = (int *)((char *)&local + 16 * 1024 * 1024);
    *p = 1;
    printf("%d\n", *p);
    return argument;
}

int main(void) {
    pthread_t thread;
    pthread_create(&thread, NULL, wild, NULL);
    pthread_join(thread, NULL);
    return 0;
}
eof

for program in not_stack_overflow_null not_stack_overflow_thread; do
	echo "*** $program" 1>&2
	"$dcc" $program.c -o $program || exit 1
	(
		# the frame and the thread stack are sized from the stack limit
		ulimit -S -s 8192
		./$program 2>&1 >/dev/null |
			grep -E 'stack overflow|Runtime error|Execution stopped because' |
			sort -u 1>&2
	)
done
rm -f not_stack_overflow_null.c not_stack_overflow_null
rm -f not_stack_overflow_thread.c not_stack_overflow_thread
