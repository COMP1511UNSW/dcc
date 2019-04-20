#include <stdlib.h>
int main(void) { 
    int **a = malloc(sizeof *a);
    return **a;
}
