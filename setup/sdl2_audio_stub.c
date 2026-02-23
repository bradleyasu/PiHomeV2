// SDL2 audio device stub - prevents device enumeration and access
// Compile: gcc -shared -fPIC -o libsdl2_audio_stub.so sdl2_audio_stub.c

#include <stddef.h>
#include <stdint.h>

// Return 0 devices - prevents SDL2 from enumerating ANY audio devices
int SDL_GetNumAudioDevices(int iscapture) {
    return 0;
}

// Return NULL - no device names available
const char* SDL_GetAudioDeviceName(int index, int iscapture) {
    return NULL;
}

// Always fail to open - prevents device access even if SDL2 tries
uint32_t SDL_OpenAudioDevice(const char* device, int iscapture,
                               const void* desired, void* obtained,
                               int allowed_changes) {
    return 0; // 0 = failure in SDL2
}
