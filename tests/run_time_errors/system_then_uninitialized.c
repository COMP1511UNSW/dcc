// system() and clock() are synchronized between the dual sanitizers
// so an uninitialized variable is still detected after them
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

int clock_is_available(void) {
    clock_t c = clock();
    return c != (clock_t)-1;
}

int main(int argc, char *argv[]) {
    printf("before system\n");
    fflush(stdout);
    int status = system("echo from a child process");
    printf("system returned %d\n", status);
    printf("clock available %d\n", clock_is_available());
    int a[2];
    a[0] = 0;
    if (a[argc] > 0) {
        printf("uninitialized positive\n");
    }
    printf("after\n");
    return 0;
}
