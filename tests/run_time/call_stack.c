#include <stdlib.h>

int f3(int a) {
	int b[] = {0};
	return b[a];
}
int f2(int a) {
	return f3(a + 1);
}

int f1(int a) {
	return f2(a + 1);
}

int main(void) {
    return f1(42);
}
