#!/bin/sh
# a chdir file action means only the child can resolve the path, so dcc's
# work-around for valgrind returning 0 from posix_spawn must not resolve it
# itself when file_actions are given

mkdir -p spawn_chdir_dir
printf '#!/bin/sh\necho ran the child\n' >spawn_chdir_dir/child
chmod +x spawn_chdir_dir/child

cat >spawn_chdir.c <<eof
#include <spawn.h>
#include <stdio.h>
#include <sys/wait.h>

extern char **environ;

int main(void) {
    posix_spawn_file_actions_t actions;
    posix_spawn_file_actions_init(&actions);
    posix_spawn_file_actions_addchdir_np(&actions, "spawn_chdir_dir");
    char *argv[] = { "child", NULL };
    pid_t pid;
    int status;
    int spawn = posix_spawn(&pid, "./child", &actions, NULL, argv, environ);
    if (spawn == 0) {
        waitpid(pid, &status, 0);
    }
    int spawnp = posix_spawnp(&pid, "./child", &actions, NULL, argv, environ);
    if (spawnp == 0) {
        waitpid(pid, &status, 0);
    }
    printf("posix_spawn after chdir %d\n", spawn);
    printf("posix_spawnp after chdir %d\n", spawnp);
    return 0;
}
eof

"$dcc" -fsanitize=valgrind spawn_chdir.c -o spawn_chdir || exit 1
./spawn_chdir
rm -rf spawn_chdir_dir spawn_chdir.c spawn_chdir
