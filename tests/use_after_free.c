#include <stdlib.h>

int main(void) {
    int *p = malloc(sizeof (int *));
    *p = p;
    free(p);
    p = *p;
}
