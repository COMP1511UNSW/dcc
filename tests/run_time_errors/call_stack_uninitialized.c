#include <stdlib.h>

int f3(int *a) {
	return *a;
}
int f2(int *a) {
	return f3(a);
}

int f1(int *a) {
	return f2(a);
}

int main(int argc, char **argv) {
    int **i = (int **)malloc(2 * sizeof (int *));
    i[argc] = NULL;
    return f1(i[0]);
}
