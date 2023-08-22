#include <stdio.h>

int main(int argc, char *argv[]) { 
	int i = 0;
	const int j = 2;
	if (argc == 0) {
		i = 1;
	}
	printf("%d\n", j/i);
}

