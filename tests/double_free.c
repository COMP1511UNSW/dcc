#include <stdlib.h>

int main(void) {
    void *p = malloc(4);
    free(p);
    free(p);
}
