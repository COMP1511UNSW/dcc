//dcc_flags=--leak-check

// the leak must be reported where the student called getline,
// not inside glibc's getdelim

#include <stdio.h>

int main(void) {
    char *line = NULL;
    size_t size = 0;
    getline(&line, &size, stdin);
}
