//dcc_flags=-fsanitize=valgrind
#include <spawn.h>
int main(int argc, char*argv[]) {
	pid_t p;
	char *a[] = {"/bin/true", NULL};
	posix_spawn_file_actions_t file_actions;
    if (argc != 1) {
         posix_spawn_file_actions_init(&file_actions);
    }
	posix_spawn(&p, a[0], &file_actions, NULL, a, NULL);
}
