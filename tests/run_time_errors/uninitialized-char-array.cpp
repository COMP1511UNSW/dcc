//dcc_flags=-fsanitize=valgrind
// --memory does not detect this
#include <iostream>

int main(int argc, char **argv) { 
	char input[2][10];
	input[argc][argc] = 0;
	std::cout << input[0];
}
