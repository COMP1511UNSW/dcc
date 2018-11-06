#include <stdio.h>

int main(int argc, char **argv) { 
	fprintf(fopen("/dev/null", "r"), "Hello world\n");
}
