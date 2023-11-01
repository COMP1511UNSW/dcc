#include <stdio.h>
#include <assert.h>

int main(void) {
    assert(fileno(stdin) == 0);
    assert(fileno(stdout) == 1);
    assert(fileno(stderr) == 2);
    assert(fileno(fopen(__FILE__, "r")) == 3);
}
