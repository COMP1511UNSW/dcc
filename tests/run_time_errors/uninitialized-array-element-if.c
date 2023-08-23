//dcc_flags=
//dcc_flags=-fsanitize=memory
//dcc_flags=-fsanitize=address,memory
//dcc_flags=-fsanitize=valgrind

int main(int argc, char **argv) {
    int a[1000];
    a[42] = 42;
    if (a[argc]) {
        a[43] = 43;
    }
}
