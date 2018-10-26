#include <stdio.h>

int main(int argc, char **argv) { 
	printf("%d\n", 42 % (argc - 1));
}
