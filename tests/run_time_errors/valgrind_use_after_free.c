//dcc_flags=-fsanitize=valgrind
// the explanation must come from what valgrind says was accessed,
// not from a guess about the kind of access

#include <stdlib.h>

int main(int argc, char *argv[]) {
    int *p = (int *)malloc(4 * sizeof *p);
    p[0] = 1;
    if (argc > 0) {
        free(p);
    }
    return p[0];
}
