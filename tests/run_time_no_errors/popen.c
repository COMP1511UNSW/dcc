#include <stdio.h>
int main(void) {
    pclose(popen("echo popen", "w"));
}
