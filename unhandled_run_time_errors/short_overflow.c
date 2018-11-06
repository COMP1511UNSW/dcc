#include <stdio.h>

int main(int argc, char **argv) { 
    short s = 0;
    for (int i = 0; i < 100000; i++) {
    	s += argc;
	    printf("%d\n", s);
    }
}
