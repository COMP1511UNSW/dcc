// --memory does not detect this
#include <stdio.h>

int main(int argc, char *argv[]) {
    char input[8192];
    input[argc] = 0;
    printf("%c", input[0]);
}
