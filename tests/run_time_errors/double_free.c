#include <stdlib.h>

int main(void) {
    void *p = malloc(4);
    if (p) free(p);
    free(p);
}
