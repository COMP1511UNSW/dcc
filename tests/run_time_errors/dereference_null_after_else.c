#include <stdio.h>
int main(void) {
    int *a = NULL;
    int n = 1;
    if (n < 0) n = 0;
    else *(a + 1) = 5;
    return n;
}
