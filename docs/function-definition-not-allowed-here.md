
If you forget a curly bracket, e.g.
```c
int sum(int x, int y) {
	if (x > y) {
		return x + y;
	} else {
		return x - y;
		// <-- missing closing curly bracket
}
		
int f(int x) {
	return sum(x, x);
}
```

The compiler will give an error when the next function definition starts.

You can fix by adding the missing curly bracket (brace):

```c
int sum(int x, int y) {
	if (x > y) {
		return x + y;
	} else {
		return x - y;
	}
}
		
int f(int x) {
	return sum(x, x);
}
```
