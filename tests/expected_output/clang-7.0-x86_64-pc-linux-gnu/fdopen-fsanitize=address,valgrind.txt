//dcc_flags=-fsanitize=address,valgrind
#include <stdio.h>

int main(void) {
	extern int open(const char *pathname, int flags);
    FILE *f = fdopen(open(__FILE__, 0), "r");
    int c;
    while ((c = fgetc(f)) != EOF) {
    	putchar(c);
    }
}
