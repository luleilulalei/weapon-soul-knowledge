#pragma once

#include "sdkconfig.h"

#if CONFIG_USAKI_USE_AFE_AUDIO_PROCESSOR

#include <functional>
#include <mutex>
#include <vector>

#include "esp_afe_sr_models.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

#include "audio/audio_processor.h"

class AfeAudioProcessor : public AudioProcessor {
public:
    AfeAudioProcessor();
    ~AfeAudioProcessor() override;

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
    EventGroupHandle_t event_group_ = nullptr;
    const esp_afe_sr_iface_t *afe_iface_ = nullptr;
    esp_afe_sr_data_t *afe_data_ = nullptr;
    AudioCodec *codec_ = nullptr;
    int frame_samples_ = 0;
    bool is_speaking_ = false;
    int vad_speech_frames_ = 0;
    int vad_silence_frames_ = 0;
    TickType_t last_vad_gate_log_ = 0;
    TickType_t started_at_ticks_ = 0;
    std::vector<int16_t> input_buffer_;
    std::vector<int16_t> output_buffer_;
    std::mutex input_buffer_mutex_;
    std::function<void(std::vector<int16_t> &&data)> output_callback_;
    std::function<void(bool speaking)> vad_state_change_callback_;

    void ProcessorTask();
};

#endif
