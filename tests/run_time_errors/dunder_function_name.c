// __ is reserved for the implementation, but a student who writes it must
// still be told the error is in their function, not in its caller
#include <stdio.h>

static int __deref(int *p) {
    return *p;
}

int main(void) {
    printf("%d\n", __deref(0));
    return 0;
}
