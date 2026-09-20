//dcc_flags=
//dcc_flags=-fsanitize=address,memory
//dcc_flags=-fsanitize=valgrind

int main(int argc, char **argv) {
    int a[100];
    a[42] = 42;
    if (a[argc]) {
        a[43] = 43;
    }
}
// not run with -fsanitize=memory alone: the values displayed for a are not deterministic
