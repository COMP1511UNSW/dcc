//dcc_flags=-fsanitize=address,valgrind
#include <stdio.h>
#include <fcntl.h>

int main(void) {
    FILE *f = fdopen(open(__FILE__, O_RDONLY), "r");
    int c;
    while ((c = fgetc(f)) != EOF) {
    	putchar(c);
    }
}
