#include <stdio.h>

void g(int *p, int *q, int *r, int *s) {
    printf("%d %d %d %d\n", *p, *q, *r, *s);
}

void f(int i, int *p, int *q) {
    int j[10];
    g(p, q, &j[i], &i);
}

int main(int argc, char *argv[]) {
    int i;
    int j[10];
    int *p = &i;
    int *q = &j[argc];
    if (argc == 0) {
        i = 0;
        j[0] = 0;
    }
    f(argc, p, q);
}
