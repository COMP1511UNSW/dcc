#include <string.h>
#include <unistd.h>

int main(void) {
    char c = 'd';
    char s[5];
    strcat(s, &c);
}