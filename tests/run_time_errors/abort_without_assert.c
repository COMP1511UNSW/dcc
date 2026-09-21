// abort() reached without a failed assert() must not be blamed on assert()
#include <stdlib.h>

int main(void) {
    abort();
}
