//dcc_flags="--valgrind"
// --memory does not detects this
#include <stdio.h>

int main(int argc, char **argv) { 
	char input[2][10];
	printf("%s", input[0]);
}
