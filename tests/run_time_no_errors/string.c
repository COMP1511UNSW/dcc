#include <string.h>
#include <assert.h>

int main(int argc, char *argv[]) {
	char a[40];
	assert(a == strcpy(a, "hello"));
	assert(a == strcat(a, "there"));
	assert(strcmp("hellothere", a) == 0);
	assert(strlen(a) == 10);
	char b[40] = {0};
	assert(b == strncpy(b, "hello", argc  + 1));
	assert(strcmp(b, "he") == 0);
	assert(b == strncat(b, "there", argc  + 2));
	assert(strcmp("hethe", b) == 0);
	assert(strncmp("hehe", b, 2) == 0);
	assert(strncmp("hehe", b, 3) < 0);
	char c[40];
	assert(c + 5 == stpcpy(c, "hello"));
	assert(strcmp("hello", c) == 0);
	char d[40] = {0};
	assert(d + argc  + 1 == stpncpy(d, "hello", argc  + 1));
	assert(strcmp("he", d) == 0);
	assert(strspn("hello", "there") == 2);
	assert(strspn("hello", "HELLO") == 0);
	assert(strcspn("hello", "HELLO") == 5);
}
