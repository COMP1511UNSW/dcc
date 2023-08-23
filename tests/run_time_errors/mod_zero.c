//dcc_flags=
//dcc_flags=-fsanitize=memory
//dcc_flags=-fsanitize=valgrind

#include <stdio.h>
int main(int argc, char **argv) {
    printf("%d\n", 42 % (argc - 1));
}
