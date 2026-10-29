#pragma once

#include "audio/wake_word.h"

class NoWakeWord : public WakeWord {
public:
    esp_err_t Initialize(AudioCodec *codec) override;
    void Start() override;
    void Stop() override;
    void Feed(const std::vector<int16_t> &data) override;
    size_t GetFeedSize() const override;
    bool IsRunning() const override;
    const std::string &GetLastDetectedWakeWord() const override;
    void OnWakeWordDetected(std::function<void(const std::string &wake_word)> callback) override;

private:
    std::function<void(const std::string &wake_word)> wake_word_detected_callback_;
    std::string last_detected_wake_word_;
};
