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

int openat(int dirfd, const char *pathname, int flags, ...) {
    // Get original openat function
    static int (*real_openat)(int, const char*, int, ...) = NULL;
    if (!real_openat) {
        real_openat = dlsym(RTLD_NEXT, "openat");
    }
    
    // Block any sysfs access to card1 (our DAC)
    if (pathname && strstr(pathname, "card1")) {
        errno = ENOENT;  // No such file or directory
        return -1;
    }
    
    // Pass through to real openat for everything else
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
