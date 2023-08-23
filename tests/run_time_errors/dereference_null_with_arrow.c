#include <stdio.h>
struct list_node {
    struct list_node *next;
    int data;
};
int main(void) {
    struct list_node *a = NULL;
    a->data = 42;
}
