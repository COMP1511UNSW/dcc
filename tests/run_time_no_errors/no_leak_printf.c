//dcc_flags=--leak-check

#include <stdio.h>

int main(void) {
    printf("this causes a spurious memory leak with some libc versions\n");
}
