#include <spawn.h>
#include <stdio.h>
int main(void) {
	pid_t p = 42;
	char *a[] = {"/bin/true", NULL};
	printf("%d %d\n",  p, posix_spawn(&p, a[0], NULL, NULL, a, NULL));
}
