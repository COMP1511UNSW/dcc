struct s {
    int a;
};

typedef struct s Point;

// the size in the declaration of q is not a subscript, so no value
// may be printed for q[2]
int main(void) {
    Point q[2];
    q[0].a = 1;
    int *p = 0;
    *p = q[0].a;
    return 0;
}
