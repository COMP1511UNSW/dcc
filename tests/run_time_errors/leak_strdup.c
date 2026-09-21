//dcc_flags=--leak-check

// the leak must be reported where the student called strdup,
// not inside strdup

#include <string.h>

int main(void) {
    strdup("hello");
}
