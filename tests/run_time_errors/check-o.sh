#!/bin/bash

cat >example2.c <<eof
#include <stdio.h>
#include <stdlib.h>

struct node {
    int value;
    struct node *next;
};

int main(void) {
    struct node *new_node = malloc(sizeof(struct node));
    new_node->next = NULL;
    struct node *current = new_node->next;
    printf("%d\n", current->value);
    return 0;
}
eof

$dcc example2.c -o example2 && ./example2

rm -f example2.c example2