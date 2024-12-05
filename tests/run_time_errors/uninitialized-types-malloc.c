#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

struct i {
	int8_t i8;
	uint8_t u8;
	int32_t i32;
	uint32_t u32;
	int64_t i64;
	uint64_t u64;
	int *ip;
};

struct f {
	float f;
	double d;
	double *dp;
};

struct c {
	char c;
	char *s;
	char a[16];
};

int main(int argc, char *argv[]) {
	struct i *i = malloc(sizeof *i);
	struct f *f = malloc(sizeof *f);
	struct c *c = malloc(sizeof *c);
	if (!argc) {
		i->i8 = 1;
		f->d = 1;
		c->c = 1;
	}
	printf("%d %lf %c\n", i->i8, f->d, c->c);
}
