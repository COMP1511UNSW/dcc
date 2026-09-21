// an uninitialized array element used after deep recursion has dirtied
// the stack and printf has been called
//
// one element is assigned and the index depends on argc
// so the compilers can not warn at compile time
#include <stdio.h>

int count_down(int n) {
    char buffer[512];
    for (int i = 0; i < 512; i++) {
        buffer[i] = n;
    }
    if (n > 0) {
        return count_down(n - 1) + buffer[n];
    }
    return buffer[0];
}

int bottom(int n, int i) {
    int x[4];
    x[0] = 1;
    if (n > 0) {
        return bottom(n - 1, i);
    }
    if (x[i] > 3) {
        return 1;
    }
    return 0;
}

int main(int argc, char *argv[]) {
    printf("%d\n", count_down(500));
    printf("%d\n", bottom(20, argc));
    return 0;
}
