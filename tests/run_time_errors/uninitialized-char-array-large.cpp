// --memory does not detect this
#include <iostream>

int main(int argc, char *argv[]) {
	char input[8192];
    input[argc] = 0;
	std::cout << input[0];
}
