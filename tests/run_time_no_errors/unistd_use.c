#include <stdio.h>

int main(void) {
    extern int close(int fd);
    close(0);
}
