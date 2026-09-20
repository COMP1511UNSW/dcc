//dcc_flags=-fsanitize=valgrind
// valgrind returns 0 from posix_spawn/posix_spawnp for a program which can not
// be executed, so dcc works around it: these must be the errno values
// posix_spawn returns when the program is run without valgrind
#include <spawn.h>
#include <stdio.h>

extern char **environ;

int main(void) {
    pid_t p;
    char *a[] = { "x", NULL };
    printf("posix_spawn of a non-existent path %d\n",
           posix_spawn(&p, "/no/such/binary", NULL, NULL, a, environ));
    printf("posix_spawnp of a non-existent command %d\n",
           posix_spawnp(&p, "no_such_command_xyz", NULL, NULL, a, environ));
    printf("posix_spawnp of a non-existent path %d\n",
           posix_spawnp(&p, "./no/such/binary", NULL, NULL, a, environ));
    printf("posix_spawn of a directory %d\n",
           posix_spawn(&p, "/", NULL, NULL, a, environ));
    return 0;
}
