#include <stdio.h>
struct list_node {
    struct list_node *next;
    int data;
};
int main(void) { 
    struct list_node s1, s2  = {0};
    struct list_node *a = &s1;
    s1.next = &s2;
    a->next->next->data = 42;
}
