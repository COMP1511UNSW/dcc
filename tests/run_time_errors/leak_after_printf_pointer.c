//dcc_flags=--leak-check

// printing a pointer makes the two sanitizers write different numbers of bytes
// which must not stop valgrind's leak checking

#include <stdio.h>
#include <stdlib.h>

int main(void) {
    void *p = malloc(1);
    printf("%p\n", p);
}
