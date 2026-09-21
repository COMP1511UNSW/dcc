struct s {
    int a;
};

// the size in the declaration of v is not a subscript, so no value
// may be printed for v[3]
int main(void) {
    struct s v[3];
    v[0].a = 1;
    int *p = 0;
    *p = v[0].a;
    return 0;
}
