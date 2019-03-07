You will get this error if for example:

```c

int square(int x)
	return x * x;
}

...

int a;
a = square;
```

when you wanted to do this:

```c

int square(int x)
	return x * x;
}

...

int a;
a = square(5);
```
