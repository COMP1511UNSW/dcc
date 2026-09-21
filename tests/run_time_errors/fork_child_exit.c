// a forked child running exit runs dcc's cleanup, which waited for and then
// killed the second sanitizer the parent is still relying on: the parent then
// finished normally with the uninitialized value below undetected
//
// unistd.h is not included because that leaves only one sanitizer
#include <stdlib.h>

extern int fork(void);
extern int wait(int *status);

int main(int argc, char **argv) {
    if (fork() == 0) {
        exit(0);
    }
    int status;
    wait(&status);
    int a[100];
    a[42] = 42;
    if (a[argc]) {
        a[43] = 43;
    }
}
