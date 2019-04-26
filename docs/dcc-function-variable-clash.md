It is legal to have local variable with the same name as a function, but you can't then call the function
because  the local variable declaration hides the function.

For example:

```c
int sum(int x, int y) {
	return x + y;
}

int f(int sum) {
	int square = sum * sum;
	
	// error sum because sum is a variable 
	return sum(square, square);
}
```

You can fix the name clash by changing the name of the variable:

```c
int sum(int x, int y) {
	return x + y;
}

int f(int a) {
	int square = a * a;
	
	// error sum because sum is a variable 
	return sum(square, square);
}
```
