//dcc_flags=-pthread
// -pthread selects a single sanitizer and is accepted by the gcc checking pass
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
