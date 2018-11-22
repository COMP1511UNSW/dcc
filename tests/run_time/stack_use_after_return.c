int *f(void) {
	int i = 0;
	return &i;
}
int main(void) {
	return *f();
}
