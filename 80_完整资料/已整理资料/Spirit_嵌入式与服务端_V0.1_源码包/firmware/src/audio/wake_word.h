#pragma once

#include <functional>
#include <string>
#include <vector>

#include "audio/audio_codec.h"
#include "esp_err.h"

class WakeWord {
public:
    virtual ~WakeWord() = default;

    virtual esp_err_t Initialize(AudioCodec *codec) = 0;
    virtual void Start() = 0;
    virtual void Stop() = 0;
    virtual void Feed(const std::vector<int16_t> &data) = 0;
    virtual size_t GetFeedSize() const = 0;
    virtual bool IsRunning() const = 0;
    virtual bool IsAfeWakeWord() const { return false; }
    virtual const std::string &GetLastDetectedWakeWord() const = 0;
    virtual void OnWakeWordDetected(std::function<void(const std::string &wake_word)> callback) = 0;
};
