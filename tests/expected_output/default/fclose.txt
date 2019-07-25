#include <stdio.h>

int main(void) {
	for (int i = 0;i < 50000; i++) {
 	   fclose(fopen(__FILE__, "r"));
 	}
    FILE *f = fopen(__FILE__, "r");
    int c;
    while ((c = fgetc(f)) != EOF) {
    	putchar(c);
    }
}
