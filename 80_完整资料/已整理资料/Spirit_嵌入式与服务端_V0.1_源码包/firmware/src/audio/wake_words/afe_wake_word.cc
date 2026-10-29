#include "audio/wake_words/afe_wake_word.h"

#if CONFIG_USAKI_WAKE_WORD_USE_AFE

#include <cstring>
#include <sstream>

#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_wn_models.h"

static const char *TAG = "afe_wake_word";
static constexpr EventBits_t kDetectionRunning = BIT0;

AfeWakeWord::AfeWakeWord()
{
    event_group_ = xEventGroupCreate();
}

AfeWakeWord::~AfeWakeWord()
{
    Stop();
    if (afe_data_ != nullptr && afe_iface_ != nullptr) {
        afe_iface_->destroy(afe_data_);
        afe_data_ = nullptr;
    }
    if (owns_models_ && models_ != nullptr) {
        esp_srmodel_deinit(models_);
        models_ = nullptr;
    }
    if (event_group_ != nullptr) {
        vEventGroupDelete(event_group_);
        event_group_ = nullptr;
    }
}

esp_err_t AfeWakeWord::Initialize(AudioCodec *codec)
{
    ESP_RETURN_ON_FALSE(codec != nullptr, ESP_ERR_INVALID_ARG, TAG, "codec is null");
    codec_ = codec;

    ESP_RETURN_ON_ERROR(LoadModels(), TAG, "load wake word models failed");

    std::string input_format = BuildInputFormat();
    afe_config_t *afe_config = afe_config_init(input_format.c_str(), models_, AFE_TYPE_SR, AFE_MODE_HIGH_PERF);
    ESP_RETURN_ON_FALSE(afe_config != nullptr, ESP_ERR_NO_MEM, TAG, "afe config init failed");

    afe_config->aec_init = codec_->input_reference();
    afe_config->aec_mode = AEC_MODE_SR_HIGH_PERF;
    afe_config->afe_perferred_core = 1;
    afe_config->afe_perferred_priority = 1;
    afe_config->memory_alloc_mode = AFE_MEMORY_ALLOC_MORE_PSRAM;

    afe_iface_ = esp_afe_handle_from_config(afe_config);
    ESP_RETURN_ON_FALSE(afe_iface_ != nullptr, ESP_FAIL, TAG, "afe handle not found");
    afe_data_ = afe_iface_->create_from_config(afe_config);
    ESP_RETURN_ON_FALSE(afe_data_ != nullptr, ESP_FAIL, TAG, "afe create failed");

    BaseType_t ok = xTaskCreate([](void *arg) {
        static_cast<AfeWakeWord *>(arg)->DetectionTask();
        vTaskDelete(nullptr);
    }, "afe_wake", 4096, this, 3, &detection_task_handle_);
    ESP_RETURN_ON_FALSE(ok == pdPASS, ESP_ERR_NO_MEM, TAG, "create detection task failed");

    ESP_LOGI(TAG,
             "initialized: model=%s input_format=%s feed=%d fetch=%d",
             wakenet_model_ != nullptr ? wakenet_model_ : "",
             input_format.c_str(),
             afe_iface_->get_feed_chunksize(afe_data_),
             afe_iface_->get_fetch_chunksize(afe_data_));
    return ESP_OK;
}

void AfeWakeWord::Start()
{
    if (afe_data_ == nullptr) {
        return;
    }
    xEventGroupSetBits(event_group_, kDetectionRunning);
}

void AfeWakeWord::Stop()
{
    if (event_group_ != nullptr) {
        xEventGroupClearBits(event_group_, kDetectionRunning);
    }
    std::lock_guard<std::mutex> lock(input_buffer_mutex_);
    if (afe_data_ != nullptr && afe_iface_ != nullptr) {
        afe_iface_->reset_buffer(afe_data_);
    }
    input_buffer_.clear();
}

void AfeWakeWord::Feed(const std::vector<int16_t> &data)
{
    if (afe_data_ == nullptr || afe_iface_ == nullptr || codec_ == nullptr || !IsRunning()) {
        return;
    }

    std::lock_guard<std::mutex> lock(input_buffer_mutex_);
    if (!IsRunning()) {
        return;
    }

    input_buffer_.insert(input_buffer_.end(), data.begin(), data.end());
    const size_t chunk_size = afe_iface_->get_feed_chunksize(afe_data_) * codec_->input_channels();
    while (input_buffer_.size() >= chunk_size) {
        afe_iface_->feed(afe_data_, input_buffer_.data());
        input_buffer_.erase(input_buffer_.begin(), input_buffer_.begin() + chunk_size);
    }
}

size_t AfeWakeWord::GetFeedSize() const
{
    return afe_data_ != nullptr && afe_iface_ != nullptr ? afe_iface_->get_feed_chunksize(afe_data_) : 0;
}

bool AfeWakeWord::IsRunning() const
{
    return event_group_ != nullptr && (xEventGroupGetBits(event_group_) & kDetectionRunning) != 0;
}

const std::string &AfeWakeWord::GetLastDetectedWakeWord() const
{
    return last_detected_wake_word_;
}

void AfeWakeWord::OnWakeWordDetected(std::function<void(const std::string &wake_word)> callback)
{
    wake_word_detected_callback_ = callback;
}

esp_err_t AfeWakeWord::LoadModels()
{
    models_ = esp_srmodel_init("model");
    owns_models_ = true;
    ESP_RETURN_ON_FALSE(models_ != nullptr && models_->num >= 0, ESP_FAIL, TAG, "model partition init failed");

    ESP_LOGI(TAG, "loaded %d speech model(s)", models_->num);
    for (int i = 0; i < models_->num; ++i) {
        ESP_LOGI(TAG, "model %d: %s", i, models_->model_name[i]);
    }

    if (strlen(CONFIG_USAKI_WAKE_WORD_MODEL_NAME) > 0 &&
        esp_srmodel_exists(models_, const_cast<char *>(CONFIG_USAKI_WAKE_WORD_MODEL_NAME)) >= 0) {
        wakenet_model_ = const_cast<char *>(CONFIG_USAKI_WAKE_WORD_MODEL_NAME);
    } else {
        if (strlen(CONFIG_USAKI_WAKE_WORD_MODEL_NAME) > 0) {
            ESP_LOGW(TAG, "preferred WakeNet model not found: %s", CONFIG_USAKI_WAKE_WORD_MODEL_NAME);
        }
        wakenet_model_ = esp_srmodel_filter(models_, ESP_WN_PREFIX, nullptr);
    }
    ESP_RETURN_ON_FALSE(wakenet_model_ != nullptr, ESP_FAIL, TAG, "no WakeNet model found");

    char *words = esp_srmodel_get_wake_words(models_, wakenet_model_);
    if (words != nullptr) {
        std::stringstream ss(words);
        std::string word;
        while (std::getline(ss, word, ';')) {
            if (!word.empty()) {
                wake_words_.push_back(word);
            }
        }
    }
    if (wake_words_.empty()) {
        wake_words_.push_back(wakenet_model_);
    }

    ESP_LOGI(TAG, "selected WakeNet model: %s", wakenet_model_);
    return ESP_OK;
}

std::string AfeWakeWord::BuildInputFormat() const
{
    const int ref_num = codec_ != nullptr && codec_->input_reference() ? 1 : 0;
    const int mic_num = codec_ != nullptr ? codec_->input_channels() - ref_num : 1;
    std::string input_format;
    for (int i = 0; i < mic_num; ++i) {
        input_format.push_back('M');
    }
    for (int i = 0; i < ref_num; ++i) {
        input_format.push_back('R');
    }
    return input_format.empty() ? "M" : input_format;
}

void AfeWakeWord::DetectionTask()
{
    while (afe_data_ == nullptr || afe_iface_ == nullptr) {
        vTaskDelay(pdMS_TO_TICKS(10));
    }

    ESP_LOGI(TAG, "detection task started");
    while (true) {
        xEventGroupWaitBits(event_group_, kDetectionRunning, pdFALSE, pdTRUE, portMAX_DELAY);

        afe_fetch_result_t *res = afe_iface_->fetch_with_delay(afe_data_, portMAX_DELAY);
        if (!IsRunning() || res == nullptr || res->ret_value == ESP_FAIL) {
            continue;
        }

        StoreWakeWordData(res->data, res->data_size / sizeof(int16_t));
        if (res->wakeup_state != WAKENET_DETECTED) {
            continue;
        }

        Stop();
        last_detected_wake_word_ = WakeWordNameForIndex(res->wakenet_model_index);
        ESP_LOGI(TAG, "WakeNet detected: %s", last_detected_wake_word_.c_str());
        if (wake_word_detected_callback_) {
            wake_word_detected_callback_(last_detected_wake_word_);
        }
    }
}

void AfeWakeWord::StoreWakeWordData(const int16_t *data, size_t samples)
{
    if (data == nullptr || samples == 0) {
        return;
    }

    std::lock_guard<std::mutex> lock(wake_word_mutex_);
    wake_word_pcm_.emplace_back(data, data + samples);
    while (wake_word_pcm_.size() > 2000 / 30) {
        wake_word_pcm_.pop_front();
    }
}

const char *AfeWakeWord::WakeWordNameForIndex(int model_index) const
{
    int word_index = model_index - 1;
    if (word_index >= 0 && word_index < static_cast<int>(wake_words_.size())) {
        return wake_words_[word_index].c_str();
    }
    if (!wake_words_.empty()) {
        return wake_words_.front().c_str();
    }
    return wakenet_model_ != nullptr ? wakenet_model_ : "wake_word";
}

#endif
