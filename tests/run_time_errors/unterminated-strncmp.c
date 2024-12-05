#include <string.h>

int main(void) {
    char i[2];
    char j[2];
    i[0] = 'H';
    j[0] = 'H';
    return strncmp(i, j, 2);
}
