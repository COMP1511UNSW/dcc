// clang emits calls to __muloti4 for checked 128-bit multiplication on some
// architectures, and the libgcc it links by default does not have it,
// so dcc must link compiler-rt rather than dropping -fsanitize=undefined
//
// gcc, which dcc runs afterwards for extra checking, can not link compiler-rt
// either, so this also covers dcc ignoring that pass rather than reporting it
#include <stdio.h>

extern __int128 __muloti4(__int128 a, __int128 b, int *overflow);

int main(void) {
    int overflow = 1;
    __int128 product = __muloti4(6, 7, &overflow);
    printf("%d %d\n", (int)product, overflow);
    return 0;
}
