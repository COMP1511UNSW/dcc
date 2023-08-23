#include <stdio.h>

// check we don't shows uninformative closing braces or next function in error context
int main(int argc, char **argv) {
    int a[1000];
    if (argc > 1) {
        if (argc > 2) {
            if (argc > 3) {
                if (argc > 4) {
                    if (argc > 5) {
                    }
                }
            }
        }
    }

    a[42] = 42;
    printf("%d\n", a[argc]);
}
int f(void) {
    return 42;
}
