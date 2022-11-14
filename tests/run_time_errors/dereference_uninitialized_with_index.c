#include <stdlib.h>
int main(int argc, char*argv[]) { 
    int **a = (int **)malloc(2 * sizeof *a);
    a[argc] = NULL;
    return a[0][0];
}
