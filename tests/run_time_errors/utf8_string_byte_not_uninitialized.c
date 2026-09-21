#include <stdio.h>

// 0xaa is a valid utf-8 continuation byte, so the second byte of a character
// such as 'e-circumflex' must not be reported as an uninitialized value
int main(void) {
    char word[5] = "t\303\252e";
    int *p = NULL;
    printf("%s\n", word);
    return *p;
}
