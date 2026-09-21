//dcc_flags=-fsanitize=valgrind
//dcc_flags=-fsanitize=address
// valgrind and AddressSanitizer must give the same explanation for the
// same access past the end of malloc'ed memory

#include <stdlib.h>

int main(void) {
    int *a = malloc(4 * sizeof *a);
    a[7] = 1;
    free(a);
    return 0;
}
