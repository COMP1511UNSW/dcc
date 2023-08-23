#include <stdio.h>

int main(void) {
    FILE *f = fopen(__FILE__, "r");
    fseek(f, -10, SEEK_END);
    int c;
    while ((c = fgetc(f)) != EOF) {
        putchar(c);
    }
}
