// an uncaught exception calls abort(), but no assert() failed
#include <iostream>
#include <stdexcept>

static int get(int i) {
    if (i > 2) {
        throw std::out_of_range("index too large");
    }
    return i;
}

int main(void) {
    std::cout << get(5) << "\n";
    return 0;
}
