#pragma once

#include <atomic>
#include <mutex>
#include <functional>
#include <vector>

#include "audio/audio_processor.h"

class NoAudioProcessor : public AudioProcessor {
public:
    void Initialize(AudioCodec *codec, int frame_duration_ms, srmodel_list_t *models_list) override;
    void Feed(std::vector<int16_t> &&data) override;
    void Start() override;
    void Stop() override;
    bool IsRunning() override;
    void OnOutput(std::function<void(std::vector<int16_t> &&data)> callback) override;
    void OnVadStateChange(std::function<void(bool speaking)> callback) override;
    size_t GetFeedSize() override;
    void EnableDeviceAec(bool enable) override;

private:
    std::mutex buffer_mutex_;
    AudioCodec *codec_ = nullptr;
    int frame_samples_ = 0;
    std::vector<int16_t> output_buffer_;
    std::function<void(std::vector<int16_t> &&data)> output_callback_;
    std::function<void(bool speaking)> vad_state_change_callback_;
    std::atomic<bool> is_running_ = false;
};
