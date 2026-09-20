//dcc_flags=-lm
// linking libm must not disable the valgrind sanitizer which detects this
//
// one element is assigned and the index depends on argc
// so the compilers can not warn at compile time
#include <stdio.h>
#include <math.h>

int main(int argc, char *argv[]) {
    double x[2];
    x[0] = 4;
    printf("%f\n", sqrt(x[argc]));
    return 0;
}
