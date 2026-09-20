int main(void) { int a[10] = {0}; int i = 10; return a[i]; }
    // an error on the first line must not show lines from the end of the file
    // (a negative line number would index the end of the file)
