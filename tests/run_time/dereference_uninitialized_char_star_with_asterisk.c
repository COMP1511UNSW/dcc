#include <stdlib.h>
int main(void) { 
    char **a = malloc(sizeof *a);
    return **a;
}
