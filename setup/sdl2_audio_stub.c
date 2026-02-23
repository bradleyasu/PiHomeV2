// SDL2 audio device stub + AGGRESSIVE sysfs blocker
// Intercepts ALL possible file open operations to block card1
// Compile: gcc -shared -fPIC -Wl,--no-as-needed -o libsdl2_audio_stub.so sdl2_audio_stub.c -ldl

#define _GNU_SOURCE
#include <stddef.h>
#include <stdint.h>
#include <fcntl.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
#include <dlfcn.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <sys/stat.h>
#include <sys/types.h>

// Uncomment for debug logging (will spam journalctl)
// #define DEBUG_STUB 1

#ifdef DEBUG_STUB
#define DEBUG_LOG(fmt, ...) fprintf(stderr, "[STUB] " fmt "\n", ##__VA_ARGS__)
#else
#define DEBUG_LOG(fmt, ...) do {} while(0)
#endif

// SDL2 audio function stubs (not actually called in our case)
int SDL_GetNumAudioDevices(int iscapture) {
    return 0;
}

const char* SDL_GetAudioDeviceName(int index, int iscapture) {
    return NULL;
}

uint32_t SDL_OpenAudioDevice(const char* device, int iscapture,
                               const void* desired, void* obtained,
                               int allowed_changes) {
    return 0;
}

// =============================================================================
// AGGRESSIVE FILE OPEN INTERCEPTION - Blocks ALL access to card1
// =============================================================================

// Helper to check if path contains card1
static inline int should_block_path(const char *pathname) {
    if (!pathname) return 0;
    
    // Block any path containing "card1"
    if (strstr(pathname, "card1") != NULL) {
        DEBUG_LOG("BLOCKED: %s", pathname);
        return 1;
    }
    
    return 0;
}

// Intercept standard open()
int open(const char *pathname, int flags, ...) {
    static int (*real_open)(const char*, int, ...) = NULL;
    if (!real_open) {
        real_open = dlsym(RTLD_NEXT, "open");
    }
    
    if (should_block_path(pathname)) {
        errno = ENOENT;
        return -1;
    }
    
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode = va_arg(args, mode_t);
        va_end(args);
        return real_open(pathname, flags, mode);
    }
    
    return real_open(pathname, flags);
}

// Intercept open64()
int open64(const char *pathname, int flags, ...) {
    static int (*real_open64)(const char*, int, ...) = NULL;
    if (!real_open64) {
        real_open64 = dlsym(RTLD_NEXT, "open64");
    }
    
    if (should_block_path(pathname)) {
        errno = ENOENT;
        return -1;
    }
    
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode = va_arg(args, mode_t);
        va_end(args);
        return real_open64(pathname, flags, mode);
    }
    
    return real_open64(pathname, flags);
}

// Intercept __open_2() (fortified)
int __open_2(const char *pathname, int flags) {
    static int (*real_open_2)(const char*, int) = NULL;
    if (!real_open_2) {
        real_open_2 = dlsym(RTLD_NEXT, "__open_2");
    }
    
    if (should_block_path(pathname)) {
        errno = ENOENT;
        return -1;
    }
    
    return real_open_2(pathname, flags);
}

// Intercept __open64_2() (fortified)
int __open64_2(const char *pathname, int flags) {
    static int (*real_open64_2)(const char*, int) = NULL;
    if (!real_open64_2) {
        real_open64_2 = dlsym(RTLD_NEXT, "__open64_2");
    }
    
    if (should_block_path(pathname)) {
        errno = ENOENT;
        return -1;
    }
    
    return real_open64_2(pathname, flags);
}

// Intercept standard openat
int openat(int dirfd, const char *pathname, int flags, ...) {
    static int (*real_openat)(int, const char*, int, ...) = NULL;
    if (!real_openat) {
        real_openat = dlsym(RTLD_NEXT, "openat");
    }
    
    // Block card1 sysfs access
    if (should_block_path(pathname)) {
        errno = ENOENT;
        return -1;
    }
    
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode = va_arg(args, mode_t);
        va_end(args);
        return real_openat(dirfd, pathname, flags, mode);
    }
    
    return real_openat(dirfd, pathname, flags);
}

// Intercept fortified openat (used by gcc -D_FORTIFY_SOURCE)
int __openat_2(int dirfd, const char *pathname, int flags) {
    static int (*real_openat_2)(int, const char*, int) = NULL;
    if (!real_openat_2) {
        real_openat_2 = dlsym(RTLD_NEXT, "__openat_2");
    }
    
    if (should_block_path(pathname)) {
        errno = ENOENT;
        return -1;
    }
    
    return real_openat_2(dirfd, pathname, flags);
}

// Intercept 64-bit openat
int openat64(int dirfd, const char *pathname, int flags, ...) {
    static int (*real_openat64)(int, const char*, int, ...) = NULL;
    if (!real_openat64) {
        real_openat64 = dlsym(RTLD_NEXT, "openat64");
    }
    
    if (should_block_path(pathname)) {
        errno = ENOENT;
        return -1;
    }
    
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode = va_arg(args, mode_t);
        va_end(args);
        return real_openat64(dirfd, pathname, flags, mode);
    }
    
    return real_openat64(dirfd, pathname, flags);
}

// Intercept fortified 64-bit openat
int __openat64_2(int dirfd, const char *pathname, int flags) {
    static int (*real_openat64_2)(int, const char*, int) = NULL;
    if (!real_openat64_2) {
        real_openat64_2 = dlsym(RTLD_NEXT, "__openat64_2");
    }
    
    if (should_block_path(pathname)) {
        errno = ENOENT;
        return -1;
    }
    
    return real_openat64_2(dirfd, pathname, flags);
}

// Intercept fopen() - high-level FILE* interface
FILE* fopen(const char *pathname, const char *mode) {
    static FILE* (*real_fopen)(const char*, const char*) = NULL;
    if (!real_fopen) {
        real_fopen = dlsym(RTLD_NEXT, "fopen");
    }
    
    if (should_block_path(pathname)) {
        errno = ENOENT;
        return NULL;
    }
    
    return real_fopen(pathname, mode);
}

// Intercept fopen64()
FILE* fopen64(const char *pathname, const char *mode) {
    static FILE* (*real_fopen64)(const char*, const char*) = NULL;
    if (!real_fopen64) {
        real_fopen64 = dlsym(RTLD_NEXT, "fopen64");
    }
    
    if (should_block_path(pathname)) {
        errno = ENOENT;
        return NULL;
    }
    
    return real_fopen64(pathname, mode);
}

// Intercept access() - used to check if file exists
int access(const char *pathname, int mode) {
    static int (*real_access)(const char*, int) = NULL;
    if (!real_access) {
        real_access = dlsym(RTLD_NEXT, "access");
    }
    
    if (should_block_path(pathname)) {
        errno = ENOENT;
        return -1;
    }
    
    return real_access(pathname, mode);
}

// Intercept readlink() - might be used to resolve /proc/self/fd/* paths
ssize_t readlink(const char *pathname, char *buf, size_t bufsiz) {
    static ssize_t (*real_readlink)(const char*, char*, size_t) = NULL;
    if (!real_readlink) {
        real_readlink = dlsym(RTLD_NEXT, "readlink");
    }
    
    ssize_t result = real_readlink(pathname, buf, bufsiz);
    
    // If the link points to card1, block it
    // Check without modifying the buffer permanently
    if (result > 0) {
        // Make a temporary null-terminated copy for checking
        char temp[4096];
        size_t check_len = (result < sizeof(temp) - 1) ? result : sizeof(temp) - 1;
        memcpy(temp, buf, check_len);
        temp[check_len] = '\0';
        
        if (should_block_path(temp)) {
            DEBUG_LOG("BLOCKED readlink result: %s", temp);
            errno = ENOENT;
            return -1;
        }
    }
    
    return result;
}

// NOTE: Removed stat/lstat/access interception - too invasive and causes segfaults
// We only intercept actual file opening, not metadata/existence checks

// Constructor - called when library loads
__attribute__((constructor))
static void stub_init(void) {
    DEBUG_LOG("=== STUB LIBRARY LOADED ===");
    DEBUG_LOG("All card1 file opens will be blocked");
}

