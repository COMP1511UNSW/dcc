// a failed assert is reported with the location and variable values
// (assert is a common tool in the course, and abort is intercepted by dcc)
#include <assert.h>
#include <stdio.h>

int main(int argc, char *argv[]) {
    int x = 5;
    printf("before assert\n");
    assert(x == argc);
    printf("after assert\n");
    return 0;
}
