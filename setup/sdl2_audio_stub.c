// SDL2 audio device stub + sysfs blocker
// Prevents device enumeration and blocks sysfs access to card1
// Compile: gcc -shared -fPIC -o libsdl2_audio_stub.so sdl2_audio_stub.c -ldl

#define _GNU_SOURCE
#include <stddef.h>
#include <stdint.h>
#include <fcntl.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
#include <dlfcn.h>

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

// Intercept openat() to block sysfs access to card1
// This prevents ffpyplayer's bundled ALSA from reading:
//   /sys/devices/.../sound/card1/uevent
//   /sys/devices/.../sound/card1/controlC1/uevent
//   /sys/devices/.../sound/card1/pcmC1D0p/uevent
// Reading these files triggers a kernel uevent that corrupts the PCM5122 DAC

// Helper to check and block card1 paths
static inline int should_block_path(const char *pathname) {
    if (!pathname) return 0;
    
    // Block both relative "card1" and full paths containing "card1"
    // This catches both openat(dirfd, "card1", ...) and openat(AT_FDCWD, "/sys/.../card1/...", ...)
    if (strstr(pathname, "card1") != NULL) {
        return 1;
    }
    
    return 0;
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
