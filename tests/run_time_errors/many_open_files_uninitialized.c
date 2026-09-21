// more streams open at once than dcc's initial table of stdio cookies holds
// used to silently stop sanitizer2, which detects uninitialized variables
#include <stdio.h>

int main(int argc, char *argv[]) {
    for (int i = 0; i < 20; i++) {
        if (!fopen("/dev/null", "r")) {
            printf("fopen failed\n");
            return 1;
        }
    }
    int a[2];
    a[0] = 0;
    if (a[argc] > 0) {
        printf("uninitialized positive\n");
    }
    return 0;
}
