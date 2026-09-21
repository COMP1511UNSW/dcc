// bytes written straight to file descriptor 1 must be written once,
// by the first sanitizer only
#include <stdio.h>

// write is declared here because including unistd.h turns off the second
// sanitizer
extern long write(int fd, const void *buf, unsigned long n);

int main(void) {
    printf("printf\n");
    fflush(stdout);
    write(1, "write\n", 6);
    return 0;
}
