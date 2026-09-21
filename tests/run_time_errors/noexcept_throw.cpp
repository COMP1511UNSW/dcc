// an exception which escapes a noexcept function reaches terminate from the
// landing pad, with no __cxa_throw left on the stack
#include <stdexcept>

static int get(int i) {
    if (i > 2) {
        throw std::out_of_range("index too large");
    }
    return i;
}

static int safe_get(int i) noexcept {
    return get(i);
}

int main(void) {
    return safe_get(5);
}
