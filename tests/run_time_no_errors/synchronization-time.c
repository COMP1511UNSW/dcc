#include <stdlib.h>
#include <time.h>

int main(void) {
    exit(time(NULL) % 64);
}
