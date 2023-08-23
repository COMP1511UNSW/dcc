int main(int argc, char **argv) {
    int a[600 + argc];
    a[1000] = argc;
    return a[1000];
}
