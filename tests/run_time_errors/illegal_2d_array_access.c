#include <stdio.h>

void twod(int b[5][4]) {
    printf("%d\n", b[5][2]);
}

int main(int argc, char **argv) {
    int a[5][4] = { { 0 } };
    twod(a);
    return 0;
}
