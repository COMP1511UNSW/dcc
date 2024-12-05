//dcc_flags=
//dcc_flags=-fsanitize=address
//dcc_flags=--ifdef-main

#include <stdlib.h>
#include <stdio.h>

int main(int argc, char **argv) {
    int *a = (int *)malloc(1000 * sizeof(int));
    a[999 + argc] = 42;
    printf("%d\n", a[0]);
}
