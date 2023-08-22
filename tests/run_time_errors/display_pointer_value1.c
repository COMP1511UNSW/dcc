#include <stdio.h>


void f(int k[2][3]) {
	printf("%d\n", k[0][0]);
}

int main(int argc, char *argv[]) { 
	int j[2][3];
	if (argc == 0) {
		j[0][0] = 0;
	}
	f(j);
}

