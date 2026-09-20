// gcc rewrites this strstr into __builtin_strchr, which must not be
// mistaken for printf being rewritten into puts
#include <string.h>

int main(void) {
    char *p = NULL;
    return strstr(p, "a") != NULL;
}
