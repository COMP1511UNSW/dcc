#include <stdlib.h>
int main(int argc, char **argv) { 
    char **a = malloc(2 * sizeof *a);
    a[argc] = NULL;
    return **a;
}
