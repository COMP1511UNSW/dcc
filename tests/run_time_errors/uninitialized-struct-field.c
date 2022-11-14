int main(void) {
	struct b {int a;};
    struct b *s = (struct b *)0x5;
    return s->a;
}
