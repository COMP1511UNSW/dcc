
# Introduction

dcc compiles C programs using clang and adds explanations suitable for novice programmers
to compiler messages novice programmers are likely to encounter and not understand.

For example:

	$ dcc a.c
	a.c:3:15: warning: address of stack memory associated with local variable 'counter' returned [-Wreturn-stack-address]
	        return &counter;

	dcc explanation: you are trying to return a pointer to the local variable 'counter'.
	  You can not do this because counter will not exist after the function returns.
	  See more information here: https://comp1511unsw.github.io/dcc/stack_use_after_return.html


dcc adds code to the binary which detects run-time errors and print information
likely to be helpful to novice programmers, including 
printing values of variable in lines used near where the run-time error occurred.

For example:

    $ dcc buffer_overflow.c
    $ ./a.out
    a.c:6:3: runtime error: index 10 out of bounds for type 'int [10]'
    
    Execution stopped here in main() in buffer_overflow.c at line 6:
    
        int a[10];
        for (int i = 0; i <= 10; i++) {
    --> 	a[i] = 0;
        }

    Values when execution stopped:

    a = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0}
    i = 10

dcc can alternatively embed code to detect use of uninitialized variables
and print a message a novice programmer can hopefully understand. For example:

    $ dcc --memory uninitialized-array-element.c
    $ ./a.out
    uninitialized-array-element:6 runtime error uninitialized variable used
    
    Execution stopped here in main() in uninitialized-array-element.c at line 6:

    	int a[1000];
    	a[42] = 42;
	-->    if (a[argc]) {
        a[43] = 43;
    }

    Values when execution stopped:

    argc = 1
    a[42] = 42
    a[43] = -1094795586 <-- warning appears to be uninitialized value
    a[argc] = -1094795586 <-- warning appears to be uninitialized value

# Run-time Error Handling Implementation

* dcc by default enables clang's  AddressSanitizer (`-fsanitize=address`) and UndefinedBehaviorSanitizer (`-fsanitize=undefined`) extensions.

* dcc embeds in the binary produced a xz-compressed tar file (see [compile.py]) containing the C source files for the program and some Python code which is executed if a runtime error occurs.

* Sanitizer errors are intercepted by a shims for the function `__asan_on_error` in [main_wrapper.c].

* A set of signals produced by runtime errors are trapped by `_signal_handler` in [main_wrapper.c].

* Both functions call `_explain_error` in [main_wrapper.c] which creates a temporary directory,
extracts into it the program source and Python from the embedded tar file, and executes the Python 

* runs the Python ([start_gdb.py]) prints an eror message that a novice programmer will understand

* than starts gdb, and uses it to print current values of variable used in source lines near where the error occurred.

# Dirtying Stack Pages to Facilitat Unitialized Variable Detection

Linux initializes stack pages to zero.  As a consequence novice programmers  writing small programs with few function calls
are likely to find zero in uninitialized local variables.  This often results in apparently correct behaviour from a
invalid program with uninitialized local variables.

dcc embeds code in the binary which initializes the first few megabytes of the the stack to 0xbe (see `clear-stack` in [main_wrapper.c].

When printing variable values, after a dcc warns the user if a variable looks to consist of 0xbe bytes that is likely uninitialized.

# Valgrind

dcc can alternatively embed code in the binary to run valgrind instead of the binary:

    $ dcc --valgrind buffer_overflow.c
    $ ./a.out
    Runtime error: uninitialized variable accessed.
    
    Execution stopped here in main() in uninitialized-array-element.c at line 6:

    	int a[1000];
    	a[42] = 42;
	-->    if (a[argc]) {
        a[43] = 43;
    }

    Values when execution stopped:

    argc = 1
    a[42] = 42
    a[43] = 0
    a[argc] = 0

valgrind is slower but picks up more uninitialized variable errors that MemorySanitizer.


# Build Instructions

	$ git clone https://github.com/COMP1511UNSW/dcc
	$ cd dcc
	$ make
	$ cp -p ./dcc /usr/local/bin/dcc
	
# Dependencies

clang, python3, gdb, valgrind 

# Author

Andrew Taylor (andrewt@unsw.edu.au)

Except help_cs50.py  is almost entirely from  https://github.com/cs50/help50-server/blob/master/helpers/clang.py

# License

GPLv3

