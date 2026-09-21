//dcc_flags=-fsanitize=address
// spawn.h leaves dcc a single sanitizer anyway, naming it keeps the note
// about uninitialized variables out of this test's output
#include <spawn.h>
#include <assert.h>
int main(void) {
    pid_t p;
    char *a[] = { "/bin/true", NULL };
    assert(0 == posix_spawn(&p, a[0], NULL, NULL, a, NULL));
    assert(0 == posix_spawnp(&p, "true", NULL, NULL, a, NULL));
}
