//dcc_flags=--leak-check

#include <stdlib.h>

int main(void) {
    int *p = malloc(sizeof(*p));
    free(p);
}
