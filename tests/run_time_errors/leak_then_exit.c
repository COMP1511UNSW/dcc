//dcc_flags=--leak-check

#include <stdlib.h>

int main(void) {
	char *p = (char *)malloc(1);
	exit(!p);
}
