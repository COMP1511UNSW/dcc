//dcc_flags=-fsanitize=valgrind
#include <spawn.h>
int main(void) {
	pid_t p;
	char *a[] = {"/bin/true", NULL};
	posix_spawn_file_actions_t file_actions;
	posix_spawn(&p, a[0], &file_actions, NULL, a, NULL);
}
