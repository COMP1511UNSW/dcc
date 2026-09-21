// printing a pointer must not stop valgrind's uninitialized value checking

#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int *a = malloc(sizeof *a);
    printf("%p\n", a);
    if (*a > 10) {
        printf("big\n");
    }
}
