#include <stdio.h>

#define ARRAY_SIZE 1000

int main(int argc, char **argv) { 
    int a[ARRAY_SIZE];
    int i;
    
    for (i = 0; i < ARRAY_SIZE; i++) {
		a[i+argc] = i+argc;
    }
    return a[0];
}