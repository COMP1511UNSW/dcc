//dcc_flags="-pthread -fsanitize=address"
// -pthread selects a single sanitizer and is accepted by the gcc checking pass
// naming the sanitizer keeps the note about uninitialized variables out of
// this test's output
#include <stdio.h>
#include <pthread.h>

void *run(void *argument) {
    printf("in thread %s\n", (char *)argument);
    return NULL;
}

int main(void) {
    pthread_t thread;
    pthread_create(&thread, NULL, run, "one");
    pthread_join(thread, NULL);
    return 0;
}
