#include <stdio.h>
#include <assert.h>

int main(void) {
    FILE *f = fopen("tmp.1", "w");
    fclose(f);
    remove("tmp.2");
    rename("tmp.1", "tmp.2");
    assert(fopen("tmp.2", "r"));
    remove("tmp.2");
}
