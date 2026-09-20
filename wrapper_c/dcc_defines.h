// The choices dcc makes when it compiles a program.
//
// When dcc compiles this code it writes a header defining these and passes it
// with -include, so every definition below is only a default.  The defaults
// mean the wrapper source can be compiled, opened in an editor or checked by
// an analyser without dcc having to generate anything.  To check it by hand:
//
//   cat wrapper_c/dcc_main.c wrapper_c/dcc_dual_sanitizers.c wrapper_c/dcc_util.c
//   wrapper_c/dcc_check_output.c wrapper_c/dcc_save_stdin.c
//
//  in that order, piped into:
//
//   clang -fsyntax-only -Wall -Wextra -D_GNU_SOURCE
//   -include wrapper_c/dcc_defines.h -x c -
//
// tests/check_wrapper_warnings.sh does this for every combination of sanitizers.

#ifndef DCC_DEFINES_H
#define DCC_DEFINES_H

#define DCC_STRINGIFY_(x) #x
#define DCC_STRINGIFY(x) DCC_STRINGIFY_(x)

// the sanitizers this code can be compiled for
#define ADDRESS 1
#define MEMORY 2
#define VALGRIND 3

// which one this copy is compiled for, and its name for the environment
#ifndef DCC_SANITIZER
#define DCC_SANITIZER ADDRESS
#endif
#ifndef DCC_SANITIZER_NAME
#define DCC_SANITIZER_NAME "ADDRESS"
#endif

// with two sanitizers the program is run twice, in step, by two processes
#ifndef DCC_N_SANITIZERS
#define DCC_N_SANITIZERS 1
#endif
#ifndef DCC_SANITIZER_2
#define DCC_SANITIZER_2 VALGRIND
#endif
#ifndef DCC_I_AM_SANITIZER1
#define DCC_I_AM_SANITIZER1 1
#endif
#ifndef DCC_I_AM_SANITIZER2
#define DCC_I_AM_SANITIZER2 0
#endif
// names the process in debugging output
#ifndef DCC_WHICH_SANITIZER
#define DCC_WHICH_SANITIZER "sanitizer1"
#endif

// --leak-check, as a number for the sanitizers and a word for valgrind
#ifndef DCC_LEAK_CHECK
#define DCC_LEAK_CHECK 0
#endif
#ifndef DCC_LEAK_CHECK_YES_NO
#define DCC_LEAK_CHECK_YES_NO "no"
#endif

// compare the program's output with DCC_EXPECTED_STDOUT
#ifndef DCC_CHECK_OUTPUT
#define DCC_CHECK_OUTPUT 1
#endif

// --use-after-return, which stops the stack being initialized
#ifndef DCC_STACK_USE_AFTER_RETURN
#define DCC_STACK_USE_AFTER_RETURN 0
#endif

// bytes of input kept, to give to a runtime helper; zero keeps none
#ifndef DCC_SAVE_STDIN_BUFFER_SIZE
#define DCC_SAVE_STDIN_BUFFER_SIZE 10240
#endif

// the program is C++, so cin, cout and cerr are redirected too
#ifndef DCC_CPP_MODE
#define DCC_CPP_MODE 0
#endif

// funopen instead of fopencookie, on systems which have no fopencookie
#ifndef DCC_USE_FUNOPEN
#define DCC_USE_FUNOPEN 0
#endif

// UndefinedBehaviorSanitizer is in use, so its reports can be intercepted
#ifndef DCC_UBSAN_IN_USE
#define DCC_UBSAN_IN_USE 1
#endif

// work around posix_spawn under valgrind
#ifndef DCC_WRAP_POSIX_SPAWN
#define DCC_WRAP_POSIX_SPAWN 0
#endif

// some sanitizer interfaces are only available in later versions
#ifndef DCC_CLANG_VERSION_MAJOR
#define DCC_CLANG_VERSION_MAJOR 19
#endif

// dcc's own debugging output is compiled in
#ifndef DCC_DEBUG_BUILD
#define DCC_DEBUG_BUILD 0
#endif

// where dcc was run from, and the valgrind suppressions file to use
#ifndef DCC_PATH_LITERAL
#define DCC_PATH_LITERAL "/usr/local/bin/dcc"
#endif
#ifndef DCC_SUPPRESSIONS_FILE
#define DCC_SUPPRESSIONS_FILE "/dev/null"
#endif

// the command which reads valgrind's output and explains what it reports
#ifndef DCC_MONITOR_VALGRIND
#define DCC_MONITOR_VALGRIND "true"
#endif

// values --embedded_environment_variable asked to be set in the program
#ifndef DCC_SET_EMBEDDED_ENVIRONMENT_VARIABLES
#define DCC_SET_EMBEDDED_ENVIRONMENT_VARIABLES() do { } while (0)
#endif

#endif
