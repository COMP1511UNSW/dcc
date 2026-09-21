#!/bin/sh
# an error in a function in a second source file shows that file's source
# and a call traceback into main

cat >list.h <<eof2
struct node {
    int value;
    struct node *next;
};
int sum_list(struct node *head);
eof2

cat >list.c <<eof2
#include "list.h"
int sum_list(struct node *head) {
    int total = 0;
    struct node *p = head;
    while (total < 100) {
        total += p->value;
        p = p->next;
    }
    return total;
}
eof2

cat >main.c <<eof2
#include <stdio.h>
#include "list.h"
int main(void) {
    struct node last = {42, NULL};
    struct node first = {1, &last};
    printf("%d\n", sum_list(&first));
    return 0;
}
eof2

"$dcc" main.c list.c -o multi_file || exit 1
./multi_file
rm -f list.h list.c main.c multi_file
