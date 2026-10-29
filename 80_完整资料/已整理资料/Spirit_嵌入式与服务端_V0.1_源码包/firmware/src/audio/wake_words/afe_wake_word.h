#pragma once

#include "sdkconfig.h"

#if CONFIG_USAKI_WAKE_WORD_USE_AFE

#include <condition_variable>
#include <deque>
#include <functional>
#include <mutex>
#include <string>
#include <vector>

#include "audio/wake_word.h"
#include "esp_afe_sr_models.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"
#include "model_path.h"

class AfeWakeWord : public WakeWord {
public:
    AfeWakeWord();
    ~AfeWakeWord() override;

    esp_err_t Initialize(AudioCodec *codec) override;
    void Start() override;
    void Stop() override;
    void Feed(const std::vector<int16_t> &data) override;
    size_t GetFeedSize() const override;
    bool IsRunning() const override;
    bool IsAfeWakeWord() const override { return true; }
    const std::string &GetLastDetectedWakeWord() const override;
    void OnWakeWordDetected(std::function<void(const std::string &wake_word)> callback) override;

private:
    AudioCodec *codec_ = nullptr;
    srmodel_list_t *models_ = nullptr;
    bool owns_models_ = false;
    const esp_afe_sr_iface_t *afe_iface_ = nullptr;
    esp_afe_sr_data_t *afe_data_ = nullptr;
    char *wakenet_model_ = nullptr;
    std::vector<std::string> wake_words_;
    EventGroupHandle_t event_group_ = nullptr;
    TaskHandle_t detection_task_handle_ = nullptr;
    std::function<void(const std::string &wake_word)> wake_word_detected_callback_;
    std::string last_detected_wake_word_;
    std::vector<int16_t> input_buffer_;
    mutable std::mutex input_buffer_mutex_;
    std::deque<std::vector<int16_t>> wake_word_pcm_;
    std::mutex wake_word_mutex_;

    esp_err_t LoadModels();
    std::string BuildInputFormat() const;
    void DetectionTask();
    void StoreWakeWordData(const int16_t *data, size_t samples);
    const char *WakeWordNameForIndex(int model_index) const;
};

#endif
