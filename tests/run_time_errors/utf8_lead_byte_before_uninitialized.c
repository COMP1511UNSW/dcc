#include <stdio.h>

// the mirror of utf8_string_byte_not_uninitialized.c: \377 is not a utf-8 lead
// byte, and \303 starts a character the 0xaa fill can not complete, so neither
// may hide a byte dcc should report as uninitialized
int main(void) {
    char high[8];
    char lead[8];
    high[0] = (char)0xFF;
    lead[0] = (char)0xC3;
    int *p = NULL;
    printf("%d %d\n", high[0], lead[0]);
    return *p;
}
