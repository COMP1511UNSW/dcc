//dcc_flags=--valgrind
//dcc_flags=--memory

#include <stdio.h>

int main(int argc, char **argv) { 
	int a[1000];
  	a[42] = 42;
  	printf("%d\n", a[argc]);
}
