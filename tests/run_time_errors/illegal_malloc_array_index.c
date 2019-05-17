//dcc_flags=
//dcc_flags=-fsanitize=address
//dcc_flags=--ifdef-main

#include <stdlib.h>

int main(int argc, char **argv) { 
	int *a = malloc(1000 * sizeof (int));
	a[999 + argc] = 42;
	return 0;
}
