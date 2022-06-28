int main(void) {
    struct {int a;} *s = (void *)0x5;
    return s->a;
}
