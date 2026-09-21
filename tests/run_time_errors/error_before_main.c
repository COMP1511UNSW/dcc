// a run-time error in a constructor function happens before __wrap_main,
// so nothing has recorded where the program is or which process it is,
// and the student was shown nothing at all

__attribute__((constructor)) static void initialize(void) {
    int *p = 0;
    *p = 1;
}

int main(void) {
    return 0;
}
