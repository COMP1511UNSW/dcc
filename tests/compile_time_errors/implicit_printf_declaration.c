//dcc_flags=-fno-builtin
// without its builtin table clang does not call printf a library function,
// and printf must not then be reported as a misspelling of itself
int main(void) {
    printf("hello\n");
}
