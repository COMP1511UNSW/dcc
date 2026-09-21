// more files open at once than dcc's initial table of stream cookies holds,
// so cookies are allocated for them and the program runs correctly
#include <stdio.h>
#include <stdlib.h>

#define N 24

int main(int argc, char *argv[]) {
    FILE *f[N];
    char name[32];
    for (int i = 0; i < N; i++) {
        snprintf(name, sizeof name, "tmp_file_%d.txt", i);
        f[i] = fopen(name, "w");
        if (f[i] == NULL) {
            printf("fopen %d failed\n", i);
            return 1;
        }
        fprintf(f[i], "file %d\n", i);
    }
    for (int i = 0; i < N; i++) {
        fclose(f[i]);
    }
    int n_correct = 0;
    for (int i = 0; i < N; i++) {
        snprintf(name, sizeof name, "tmp_file_%d.txt", i);
        FILE *g = fopen(name, "r");
        int j = -1;
        if (g != NULL && fscanf(g, "file %d", &j) == 1 && j == i) {
            n_correct++;
        }
        if (g != NULL) {
            fclose(g);
        }
        remove(name);
    }
    printf("%d of %d files correct\n", n_correct, N);
    return 0;
}
