#if DCC_SAVE_STDIN_BUFFER_SIZE

unsigned int __dcc_save_stdin_buffer_size = DCC_SAVE_STDIN_BUFFER_SIZE;
unsigned int __dcc_save_stdin_n_bytes_seen = 0;
char __dcc_save_stdin_buffer[DCC_SAVE_STDIN_BUFFER_SIZE];

static void __dcc_save_stdin(const char *buf, size_t size) {
    for (size_t i = 0; i < size; i++) {
        __dcc_save_stdin_buffer[__dcc_save_stdin_n_bytes_seen++ % DCC_SAVE_STDIN_BUFFER_SIZE] = buf[i];
    }
    debug_printf(3, "__dcc_save_stdin_buffer %d\n", (int)__dcc_save_stdin_n_bytes_seen);
}

#else

static void __dcc_save_stdin(const char *buf, size_t size) {
    (void)buf; // avoid unused parameter warning
    (void)size; // avoid unused parameter warning
}

#endif
