// the caret the compiler prints is positioned by how wide characters are,
// not by how many there are, so the word dcc names must survive one which
// prints two columns wide earlier on the same line
#include <stdio.h>

int main(void) {
    int marks;
    scanf("成绩%d", marks);
    return 0;
}
