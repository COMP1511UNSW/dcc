#include <stdio.h>
int main(int argc, char **argv) {
    int x[2];
    x[argc] = 1;
    printf("%d\n", (x[0] - 1)* 8);
}
