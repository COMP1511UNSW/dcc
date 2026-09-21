// an uninitialized array element used after a function with a large stack
// frame has returned and printf has been called: the stack below main must
// be re-initialized so the uninitialized value is displayed as such
//
// one element is assigned and the index depends on argc
// so the compilers can not warn at compile time
#include <stdio.h>

int fill(int n) {
    int big[10000];
    for (int i = 0; i < 10000; i++) {
        big[i] = i;
    }
    return big[n];
}

int probe(int n) {
    int arr[2000];
    arr[0] = 7;
    if (arr[n] > 3) {
        return 1;
    }
    return 0;
}

// probe is called via a function whose frame covers the stack used by
// printf's own frame, which is not re-initialized, so probe's frame is clean
int call_probe(int n) {
    char pad[1024];
    pad[0] = 0;
    return probe(n) + pad[0];
}

int main(int argc, char *argv[]) {
    printf("%d\n", fill(argc + 2));
    printf("%d\n", call_probe(argc * 1000));
    return 0;
}
