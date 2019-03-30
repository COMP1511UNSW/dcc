#include <stdio.h>
//dcc_flags=
//dcc_flags=--memory
//dcc_flags=--valgrind

int main(int argc, char **argv) { 
	printf("%d\n", 42 % (argc - 1));
}
