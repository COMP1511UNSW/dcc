#include <stdio.h>
#include <stdlib.h>
struct list_node {
    struct list_node *next;
    int data;
};
int main(void) { 
    struct list_node *a = malloc(sizeof *a);
    a->next =  malloc(sizeof *a);
    a->next->next->data = 42;
}
