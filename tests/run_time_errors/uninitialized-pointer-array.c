#include <stdio.h>

int main(int argc, char *argv[]) {
    char *p[2];
    p[argc] = NULL;
    printf("%s", p[0]);
}
