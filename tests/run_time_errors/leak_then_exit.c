//dcc_flags=--leak-check

#include <stdlib.h>

int main(void) {
	char *p = malloc(1);
	exit(!p);
}
