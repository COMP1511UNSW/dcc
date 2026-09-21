// a function whose name starts with _ is a student's, not the library's,
// so the error must be reported in it, with its variables and the traceback
#include <stdio.h>

static int _deref(int *p) {
    return *p;
}

int main(void) {
    printf("%d\n", _deref(0));
    return 0;
}
