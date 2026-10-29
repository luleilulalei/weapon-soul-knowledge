#pragma once

#include <cstdint>
#include <vector>

#include "audio/audio_codec.h"
#include "drivers/max98357a.h"

class UsakiAudioCodec : public AudioCodec {
public:
    UsakiAudioCodec();
    ~UsakiAudioCodec() override;

    void Start() override;
    bool started() const { return started_; }
    void EnableInput(bool enable) override;
    void EnableOutput(bool enable) override;
    void FlushOutput() override;

protected:
    int Read(int16_t *dest, int samples) override;
    int Write(const int16_t *data, int samples) override;

private:
    bool started_ = false;
    max98357a_handle_t amp_ = nullptr;

    std::vector<int16_t> output_stereo_;
};
