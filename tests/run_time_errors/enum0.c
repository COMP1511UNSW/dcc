#include <stdio.h>

enum a {A,B};

int main(int argc, char *argv[]) { 
	enum a i = A;
	if (argc == 0) {
		i = B;
	}
	printf("%d\n", 2/i);
}

