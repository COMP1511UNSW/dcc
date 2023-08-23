#include <stdlib.h>
int main(int argc, char **argv) {
    char **a = (char **)malloc(2 * sizeof *a);
    a[argc] = NULL;
    return **a;
}
