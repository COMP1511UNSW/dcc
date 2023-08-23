int main(void) {
    int i, a[1000], sum = 0;
    a[42] = 42;
    for (i = 0; i < 1000; i++) {
        sum += a[i] % 2;
    }
    if (sum < 1000) {
        return sum;
    }
    return 0;
}
