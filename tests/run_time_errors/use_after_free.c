#include <stdlib.h>

int main(int argc, char *argv[]) {
    int *p = (int *)malloc(sizeof(int *));
    *p = 1;
    if (argc > 0) {
        free(p);
    }
    return *p;
}
