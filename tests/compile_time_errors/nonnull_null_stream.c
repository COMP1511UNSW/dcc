// the NULL here is the stream, not a string being printed
#include <stdio.h>

int main(void) {
    FILE *f = NULL;
    fputs("x", f);
    return 0;
}
