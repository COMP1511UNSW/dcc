You are not permitted to assign arrays in C.

You can NOT do this:

```c
#define ARRAY_SIZE 10

int array1[ARRAY_SIZE] = {0,1,2,3,4,5,6,7,8,9};
int array2[ARRAY_SIZE];

array2 = array1;
```

You can instead use a loop to copy each array element individually.

```c

#define ARRAY_SIZE 10

int array1[ARRAY_SIZE] = {0,1,2,3,4,5,6,7,8,9};
int array2[ARRAY_SIZE];


for (int i = 0; i < 10; i++) {
	array2[ARRAY_SIZE] = array1[ARRAY_SIZE];
}
```
