//dcc_flags=--leak-check

// a leak allocated by a function whose name begins with an underscore
// the filter which drops leaks inside library internals matched any name
// starting with an underscore, so this leak was silently not reported
#include <stdio.h>
#include <stdlib.h>

static void _allocate(void) {
    int *numbers = malloc(16 * sizeof *numbers);
    numbers[0] = 1;
    printf("%d\n", numbers[0]);
}

int main(void) {
    _allocate();
    return 0;
}
