// the C++ form of error_before_main.c: the constructor of a global object
// runs before main, which is the ordinary case for a global in C++

struct counter {
    counter() {
        int *p = 0;
        *p = 1;
    }
};

static counter c;

int main(void) {
    return 0;
}
