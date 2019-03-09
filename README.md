
# Introduction

dcc compiles C program using clang and adds explanations suitable for novice programmers
to many of the compiler messages novice programmers are likely to encounter and not understand.

For example:

	$ dcc a.c
	a.c:3:15: warning: address of stack memory associated with local variable 'counter' returned [-Wreturn-stack-address]
	        return &counter;

	dcc explanation: you are trying to return a pointer to the local variable 'counter'.
	  You can not do this because counter will not exist after the function returns.
	  See more information here: https://comp1511unsw.github.io/dcc/stack_use_after_return.html

dcc also (by default) enables clang's  AddressSanitizer (-fsanitize=address) and UndefinedBehaviorSanitizer (-fsanitize=undefined) extensions.

dcc embeds the binary produced a compressed tar file, containing the C source files for the program and some Python code.

dcc adds code to the binary which if a runtime errors occurs

* intercepts it (AddressSanitizer error messages are incomprehensible to novice programmers

* extracts the program source and Python into a temporary directory

* runs the Python

* the Python code prints an eror message that a novice programmer will understand

* than starts gdb and used it to print values of variable in lines near where the rror occurred.

For example:

    $ dcc buffer_overflow.c
    $ ./a.out
    a.c:6:3: <span style="color: red">runtime error</span>: index 10 out of bounds for type 'int [10]'
    
    Execution stopped here in main() in <span style="color: red">buffer_overflow.c</span> at <span style="color: red">line 6</span>:
    
        int a[10];
        for (int i = 0; i <= 10; i++) {
    <span style="color: red">-->        a[i] = 0;</span>
        }

    <span style="color: blue">Values when execution stopped:</span>

    a = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0}
    i = 10

dcc can instead enable clang's MemorySanitizer (-fsanitize=memory) 

    $ dcc --memory uninitialized-array-element.c
    $ ./a.out
    uninitialized-array-element:6 <span style="color: red">runtime error uninitialized variable used</span>
    
    Execution stopped here in main() in <span style="color: red">uninitialized-array-element.c</span> at <span style="color: red">line 6</span>:

    int a[1000];
    a[42] = 42;
<span style="color: red">-->    if (a[argc]) {</span>
        a[43] = 43;
    }

    <span style="color: blue">Values when execution stopped:</span>

    argc = 1
    a[42] = 42
    a[43] = -1094795586 <span style="color: red"><-- warning appears to be uninitialized value</span>
    a[argc] = -1094795586 <span style="color: red"><-- warning appears to be uninitialized value</span>

dcc embeds code in the binary which initialize the first few megabytes of the the stack to 0xbe
and warns the user if a variable contains 0xbe bytes that is likely uninitialized.

Linux initializes stack pages to zero so novice programmers  writing small programs with few function calls
effectively otherwise are likely to find zero in uninitialized local variables.

dcc can alternatively embed code in the binary to run valgrind instead of the binary:

    $ dcc --valgrind buffer_overflow.c
    $ ./a.out
    Runtime error: uninitialized variable accessed.
    
    Execution stopped here in main() in <span style="color: red">uninitialized-array-element.c</span> at <span style="color: red">line 6</span>:

    int a[1000];
    a[42] = 42;
<span style="color: red">-->    if (a[argc]) {</span>
        a[43] = 43;
    }

    <span style="color: blue">Values when execution stopped:</span>

    argc = 1
    a[42] = 42
    a[43] = 0
    a[argc] = 0

valgrind is slower but picks up a larger range of uninitialized variable errors.

# Build Instructions

	$ git clone https://github.com/COMP1511UNSW/dcc
	$ cd dcc
	$ make
	$ cp -p ./dcc /usr/local/bin/bin
	
# Dependencies

clang, python3, gdb, valgrind 

# Author

Andrew Taylor (andrewt@unsw.edu.au)

# License

To be Added
