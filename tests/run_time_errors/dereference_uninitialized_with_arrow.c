#include <stdio.h>
#include <stdlib.h>
struct list_node {
    struct list_node *next;
    int data;
};
int main(int argc, char **argv) { 
    struct list_node *a = (struct list_node *)malloc(2 * sizeof *a);
    if (argc != 1) {
        a->next = NULL;
    }
    a->next->data = 42;
}
