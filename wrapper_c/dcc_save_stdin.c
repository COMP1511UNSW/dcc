#if __SAVE_STDIN_BUFFER_SIZE__

unsigned int __dcc_save_stdin_buffer_size = __SAVE_STDIN_BUFFER_SIZE__;
unsigned int __dcc_save_stdin_n_bytes_seen = 0;
char __dcc_save_stdin_buffer[__SAVE_STDIN_BUFFER_SIZE__];

static void __dcc_save_stdin(const char *buf, size_t size) {
    for (size_t i = 0; i < size; i++) {
        __dcc_save_stdin_buffer[__dcc_save_stdin_n_bytes_seen++ % __SAVE_STDIN_BUFFER_SIZE__] = buf[i];
    }
    debug_printf(3, "__dcc_save_stdin_buffer %d\n", (int)__dcc_save_stdin_n_bytes_seen);
}

#else

static void __dcc_save_stdin(const char *buf, size_t size) {
    (void)buf; // avoid unused parameter warning
    (void)size; // avoid unused parameter warning
}

#endif
