#include <stdio.h>
int main(void) {
    int *a = NULL;
    int n = 1;
    if (n > 0) *(a + 1) = 5;
    return 0;
}
