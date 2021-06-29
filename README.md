
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


dcc adds code to the binary which detects run-time errors and prints information
likely to be helpful to novice programmers, including
printing values of variable in lines used near where the run-time error occurred.

For example:

    $ dcc buffer_overflow.c
    $ ./a.out
    a.c:6:3: runtime error: index 10 out of bounds for type 'int [10]'
    
    Execution stopped here in main() in buffer_overflow.c at line 6:
    
        int a[10];
        for (int i = 0; i <= 10; i++) {
    -->     a[i] = i * i;
        }
    }
    
    Values when execution stopped:
    
    a = {0, 1, 4, 9, 16, 25, 36, 49, 64, 81}
    i = 10

dcc also embeds code to detect use of uninitialized variables
and print a message a novice programmer can hopefully understand. For example:

    $ dcc uninitialized.c
    $ ./a.out
    uninitialized.c:6 runtime error uninitialized variable used
    
    Execution stopped here in main() in uninitialized.c at line 6:

        int a[1000];
        a[42] = 42;
    -->    if (a[argc]) {
        a[43] = 43;
    }

    Values when execution stopped:

    argc = 1
    a[42] = 42
    a[43] = <uninitialized value>
    a[argc] = <uninitialized value>

Uninitialized variables are detected by running valgrind simultaneously as a separate process.

The synchronisation of the 2 processes is only effective for the standard C library (signal.h and threads.h excepted).
which should include almost all typical programs writen by novice programmers.
f synchronisation is lost the 2nd process should terminate silently.

If libraries other the standard C library are used, uninitialized variables does not occur.
 
# Leak checking

dcc can also embed code to check for memory-leaks:

    $ dcc  --leak-check leak.c
    $ ./a.out
    Error: free not called for memory allocated with malloc in function main in leak.c at line 3.


# Output checking

dcc can check a program's output is correct.  If a program outputs an incorrect line, the program is stopped.  A description of why the output is incorrect is printed.  The current execution location is shown with the current values of variables & expressions.

The environment variable DCC_EXPECTED_STDOUT should be set to the expected output.

If `DCC_IGNORE_CASE` is true, case is ignored when checking expected output.  Default false.

`DCC_IGNORE_WHITE_SPACE` is true, white space is ignored when checking expected output.  Default false.

`DCC_IGNORE_TRAILING_WHITE_SPACE` is true, trailing white space is ignored when checking expected output.   Default true.

`DCC_IGNORE_EMPTY_LINES` is true, empty lines are ignored when checking expected output.  Default false.

`DCC_COMPARE_ONLY_CHARACTERS` is set to a non-empty string, the characters not in the string are ignored when checking expected output. New-lines can not be ignored.

`DCC_IGNORE_CHARACTERS` is set to a non-empty string, the characters in the string are ignored when checking expected output. New-lines can not be ignored.

`DCC_IGNORE_CHARACTERS` and `DCC_IGNORE_WHITE_SPACE`  take precedence over `DCC_COMPARE_ONLY_CHARACTERS`

Environment variables are considered true if their value is a non-empty string starting with a character other than '0', 'f' or 'F'.  They are considered false otherwise.

# Local Variable Use After Function Return Detection

    $ dcc --use-after-return bad_function.c
    $ ./a.out
	bad_function.c:22 runtime error - stack use after return
	
	dcc explanation: You have used a pointer to a local variable that no longer exists.
	  When a function returns its local variables are destroyed.
	
	For more information see: https://comp1511unsw.github.io/dcc//stack_use_after_return.html
	Execution stopped here in main() in bad_function at line 22:
	
	
		int *a = f(42);
	-->	printf("%d\n", a[0]);
	}


valgrind also usually detect this type of error, e.g.:

    $ dcc --use_after_return bad_function.c
    $ ./a.out
	Runtime error: access to function variables after function has returned
	You have used a pointer to a local variable that no longer exists.
	When a function returns its local variables are destroyed.
	
	For more information see: https://comp1511unsw.github.io/dcc//stack_use_after_return.html'
	
	
	Execution stopped here in main() in tests/run_time/bad_function.c at line 22:
	
	
	int main(void) {
	-->	printf("%d\n", *f(50));
	}

# Installation

* Installation on Linux and Windows Subsystem for Linux
	
	```bash
	curl -L https://github.com/COMP1511UNSW/dcc/releases/download/2.7.4/dcc_2.7.4_all.deb -o /tmp/dcc_2.7.4_all.deb
	sudo apt install /tmp/dcc_2.7.4_all.deb
    # on WSL (not Linux) this might be necessary to run programs
	sudo bash -c "echo 0 > /proc/sys/kernel/yama/ptrace_scope;echo 1 >/proc/sys/vm/overcommit_memory"
	```

	Ubuntu UndefinedSanitizer builds appears not to allow __ubsan_on_report to be intercepted
	which degrades some error reporting
	
* Installation on  OSX

	Install python3 - see https://docs.python-guide.org/starting/install3/osx/
	Install gdb - see https://sourceware.org/gdb/wiki/PermissionsDarwin

    ```bash
	sudo curl -L https://github.com/COMP1511UNSW/dcc/releases/download/2.7.4/dcc -o /usr/local/bin/dcc
	sudo chmod o+rx  /usr/local/bin/dcc
    ```
	

# Run-time Error Handling Implementation

* dcc by default enables clang's  AddressSanitizer (`-fsanitize=address`) and UndefinedBehaviorSanitizer (`-fsanitize=undefined`) extensions.

* dcc embeds in the binary produced a xz-compressed tar file (see [compile.py]) containing the C source files for the program and some Python code which is executed if a runtime error occurs.

* Sanitizer errors are intercepted by a shim for the function `__asan_on_error` in [dcc_util.c].

* A set of signals produced by runtime errors are trapped by `_signal_handler` in [dcc_util.c].

* Both functions call `_explain_error` in [dcc_util.c] which creates a temporary directory,
extracts into it the program source and Python from the embedded tar file, and executes the Python code, which:

    * runs the Python ([start_gdb.py]) to print an error message that a novice programmer will understand, then

    * starts gdb, and uses it to print current values of variables used in source lines near where the error occurred.

#  Facilitating Clear errors from Uninitialized Variables

Linux initializes stack pages to zero.  As a consequence novice programmers  writing small programs with few function calls
are likely to find zero in uninitialized local variables.  This often results in apparently correct behaviour from a
invalid program with uninitialized local variables.

dcc embeds code in the binary which initializes the first few megabytes of the stack to 0xbe (see `clear-stack` in [dcc_util.c].

For valgrind dcc uses its malloc-fill and --free-fill options to achieve the same result see [dcc_util.c].  AddressSanitizer & MemorySanitizer use a malloc which does this by default.

When printing variable values, dcc prints ints, doubles & pointers consisting of 0xbe bytes as "<uninitialized>". 

Indirection using pointers consisting of 0xbe bytes will produced an unaligned access error from  UndefinedBehaviourSanitizer, unless the pointer is to char.  dcc intercepts these and explanations suitable for novice programmers (see  explain_ubsan_error in [drive_gdb.py])

    $ dcc dereference_uninitialized.c
    $ ./a.out
	tests/run_time/dereference_uninitialized_with_arrow.c:9:14: runtime error - accessing a field via an uninitialized pointer
	
	dcc explanation: You are using a pointer which has not been initialized
	  A common error is using p->field without first assigning a value to p.
	
	Execution stopped here in main() in dereference_uninitialized.c at line 9:
	
	int main(void) { 
	    struct list_node *a = malloc(sizeof *a);
	--> a->next->data = 42;
	}
	
	Values when execution stopped:
	
	a->next = <uninitialized value>

# Build Instructions

    $ git clone https://github.com/COMP1511UNSW/dcc
    $ cd dcc
    $ make
    $ cp -p ./dcc /usr/local/bin/dcc
 
# Release instruction

	$ ./create_github_release.py 1.0 'Initial github release of dcc'
   
# Dependencies

clang, python3, gdb, valgrind 

# Author

Andrew Taylor (andrewt@unsw.edu.au)

Except help_cs50.py  is almost entirely from  https://github.com/cs50/help50-server/blob/master/helpers/clang.py

# License

GPLv3

