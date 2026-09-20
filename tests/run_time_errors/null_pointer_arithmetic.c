#include <stdlib.h>
int main(void) {
    int *a = NULL;
    int *b = a + 1;
    return b == NULL;
}
