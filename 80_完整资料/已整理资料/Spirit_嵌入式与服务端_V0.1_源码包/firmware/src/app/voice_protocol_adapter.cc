#include "app/voice_protocol_adapter.h"

#include <cstring>

#include "app/protocol.h"
#include "app/spirit_privacy.h"
#include "app/server_call.h"
#include "esp_check.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "voice_protocol_adapter";
static constexpr int64_t kDeviceVadMinInputMs = 700;
static constexpr int64_t kDeviceVadMinSpeechMs = 180;
static constexpr int kInputEndDrainMaxWaitMs = 180;
static constexpr int kInputEndDrainPollMs = 10;
static constexpr size_t kPreVadPrerollPackets = 10;

UsakiVoiceProtocolAdapter::UsakiVoiceProtocolAdapter(AudioService *audio_service)
    : audio_service_(audio_service)
{
}

UsakiVoiceProtocolAdapter::~UsakiVoiceProtocolAdapter()
{
    Stop();
    if (send_exited_) vSemaphoreDelete(send_exited_);
}

esp_err_t UsakiVoiceProtocolAdapter::Start()
{
    ESP_RETURN_ON_FALSE(audio_service_ != nullptr, ESP_ERR_INVALID_ARG, TAG, "audio_service is null");
    if (server_ != nullptr) {
        return ESP_OK;
    }

    AudioServiceCallbacks audio_callbacks = {};
    audio_callbacks.on_send_queue_available = [this]() {
        NotifySendTask();
    };
    audio_callbacks.on_vad_change = [this](bool speaking) {
        HandleVadChange(speaking);
    };
    audio_callbacks.on_wake_word_detected = [this](const std::string &wake_word) {
        HandleWakeWordDetected(wake_word);
    };
    audio_service_->SetCallbacks(audio_callbacks);

    send_exited_ = xSemaphoreCreateBinary();
    if (!send_exited_) return ESP_ERR_NO_MEM;
    send_stopping_.store(false);
    BaseType_t ok = xTaskCreate([](void *arg) {
        static_cast<UsakiVoiceProtocolAdapter *>(arg)->SendTask();
        vTaskDelete(nullptr);
    }, "voice_send", 4096, this, 5, &send_task_handle_);
    ESP_RETURN_ON_FALSE(ok == pdPASS, ESP_ERR_NO_MEM, TAG, "create send task failed");

    usaki_server_call_config_t config = usaki_server_call_default_config();
    config.callbacks.connected = OnConnected;
    config.callbacks.disconnected = OnDisconnected;
    config.callbacks.binary = OnBinary;
    config.callbacks.error = OnError;
    config.callbacks.voice_output_start = OnVoiceOutputStart;
    config.callbacks.voice_output_end = OnVoiceOutputEnd;
    config.callbacks.voice_output_cancel = OnVoiceOutputCancel;
    config.callbacks.emotion_update = OnEmotionUpdate;
    config.callbacks.eye_animation = OnEyeAnimation;
    config.callbacks.body_action = OnBodyAction;
    config.user_ctx = this;

    esp_err_t err = usaki_server_call_init(&config, &server_);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "server_call init failed: %s", esp_err_to_name(err));
        return err;
    }

    err = usaki_server_call_start(server_);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "server_call start failed: %s", esp_err_to_name(err));
        usaki_server_call_destroy(server_);
        server_ = nullptr;
        return err;
    }

    ESP_LOGI(TAG, "started");
    return ESP_OK;
}

void UsakiVoiceProtocolAdapter::Stop()
{
    if (audio_service_ != nullptr) {
        audio_service_->EnableVoiceProcessing(false);
        audio_service_->Stop();
    }
    send_stopping_.store(true);
    if (send_task_handle_ != nullptr) {
        xTaskNotifyGive(send_task_handle_);
        xSemaphoreTake(send_exited_, portMAX_DELAY);
        send_task_handle_ = nullptr;
    }
    if (server_ != nullptr) {
        (void)usaki_server_call_stop(server_);
        (void)usaki_server_call_destroy(server_);
        server_ = nullptr;
    }
}

void UsakiVoiceProtocolAdapter::SetCallbacks(const UsakiVoiceProtocolAdapterCallbacks &callbacks)
{
    callbacks_ = callbacks;
}

esp_err_t UsakiVoiceProtocolAdapter::StartInput()
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    if (spirit_privacy_muted()) return ESP_ERR_INVALID_STATE;
    ESP_RETURN_ON_FALSE(server_ != nullptr, ESP_ERR_INVALID_STATE, TAG, "server is null");
    ESP_RETURN_ON_FALSE(usaki_server_call_is_connected(server_),
                        ESP_ERR_INVALID_STATE,
                        TAG,
                        "server is not connected");
    if (input_started_) {
        return ESP_OK;
    }

    snprintf(request_id_, sizeof(request_id_), "voice_req_%lld", (long long)usaki_protocol_now_ms());
    input_started_at_ms_ = 0;
    input_started_ = true;
    input_start_sent_ = false;
    awaiting_output_ = false;
    expected_output_request_id_[0] = '\0';
    vad_speech_seen_ = false;
    vad_speaking_ = false;
    vad_speech_started_at_ms_ = 0;
    vad_last_change_at_ms_ = 0;
    {
        std::lock_guard<std::recursive_mutex> lock(send_mutex_);
        DropSendQueueLocked("start_input");
    }
#if !CONFIG_USAKI_USE_AFE_AUDIO_PROCESSOR
    // Manual turn mode: no fake VAD callback. First key press starts an input
    // turn, next key press ends it; unchanged Opus/server packet format.
    usaki_protocol_voice_input_start_t request = usaki_protocol_voice_input_start_default();
    request.request_id = request_id_;
    request.mode = "stream";
    request.vad.enabled = false;
    request.vad.source = "manual";
    esp_err_t start_err = usaki_server_call_send_voice_input_start(server_, &request);
    if (start_err != ESP_OK) { ResetInputTracking(); return start_err; }
    input_start_sent_ = true;
    input_started_at_ms_ = usaki_protocol_now_ms();
#endif
    audio_service_->EnableVoiceProcessing(true);
    ESP_LOGI(TAG, "voice input armed, waiting for device vad speech: %s", request_id_);
    return ESP_OK;
}

esp_err_t UsakiVoiceProtocolAdapter::StopInput(const char *reason)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    if (server_ == nullptr || !input_started_) {
        return ESP_OK;
    }

    audio_service_->EnableVoiceProcessing(false);
    if (spirit_privacy_muted()) {
        std::lock_guard<std::recursive_mutex> lock(send_mutex_);
        DropSendQueueLocked("privacy_mute");
        esp_err_t err = ESP_OK;
        if (input_start_sent_ && usaki_server_call_is_connected(server_)) {
            usaki_protocol_voice_input_cancel_t cancel = usaki_protocol_voice_input_cancel_default();
            cancel.request_id = request_id_;
            cancel.reason = "privacy_mute";
            err = usaki_server_call_send_voice_input_cancel(server_, &cancel);
        }
        ResetInputTracking();
        awaiting_output_ = false;
        expected_output_request_id_[0] = '\0';
        return err;
    }

    if (!input_start_sent_) {
        {
            std::lock_guard<std::recursive_mutex> lock(send_mutex_);
            DropSendQueueLocked("stop_before_speech");
        }
        ResetInputTracking();
        ESP_LOGI(TAG, "voice input stopped before speech");
        return ESP_OK;
    }

    usaki_protocol_voice_input_end_t request = usaki_protocol_voice_input_end_default();
    request.request_id = request_id_;
    request.reason = reason != nullptr ? reason : "manual";
    request.duration_ms = (int)(usaki_protocol_now_ms() - input_started_at_ms_);

    esp_err_t err = ESP_OK;
    bool drained = !spirit_privacy_muted() && DrainInputAudioBeforeEnd();
    {
        std::lock_guard<std::recursive_mutex> lock(send_mutex_);
        if (!drained || server_ == nullptr || !usaki_server_call_is_connected(server_)) {
            DropSendQueueLocked(drained ? "stop_disconnected" : "audio_send_failed");
            ResetInputTracking();
            ESP_LOGW(TAG,
                     "voice input canceled before end: %s",
                     drained ? "websocket_disconnected" : "audio_send_failed");
            return ESP_ERR_INVALID_STATE;
        }

        err = usaki_server_call_send_voice_input_end(server_, &request);
        if (err == ESP_OK) {
            ResetInputTracking();
            awaiting_output_ = true;
            strlcpy(expected_output_request_id_, request_id_, sizeof(expected_output_request_id_));
        } else {
            DropSendQueueLocked("end_send_failed");
            ResetInputTracking();
        }
    }
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "send voice.input.end failed: %s", esp_err_to_name(err));
        return err;
    }
    ESP_LOGI(TAG, "voice input stopped");
    return ESP_OK;
}

esp_err_t UsakiVoiceProtocolAdapter::InterruptOutput(const char *reason)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    if (server_ == nullptr) {
        return ESP_OK;
    }

    audio_service_->ResetDecoder();
    usaki_protocol_voice_interrupt_t request = usaki_protocol_voice_interrupt_default();
    request.output_id = output_id_;
    request.reason = reason != nullptr ? reason : "user_interrupt";
    return usaki_server_call_send_voice_interrupt(server_, &request);
}

esp_err_t UsakiVoiceProtocolAdapter::SendWakeWordDetected(const char *wake_word, bool will_start_input)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    if (server_ == nullptr || !usaki_server_call_is_connected(server_)) {
        return ESP_ERR_INVALID_STATE;
    }

    usaki_protocol_voice_wake_detected_t request = usaki_protocol_voice_wake_detected_default();
    request.wake_word = wake_word != nullptr ? wake_word : "";
    request.will_start_input = will_start_input;
    return usaki_server_call_send_voice_wake_detected(server_, &request);
}

void UsakiVoiceProtocolAdapter::SendTask()
{
    while (true) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        if (send_stopping_.load()) {
            break;
        }
        DrainSendQueue();
    }
    xSemaphoreGive(send_exited_);
}

void UsakiVoiceProtocolAdapter::NotifySendTask()
{
    if (send_task_handle_ != nullptr) {
        xTaskNotifyGive(send_task_handle_);
    }
}

void UsakiVoiceProtocolAdapter::DrainSendQueue()
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    bool ok = false;
    {
        std::lock_guard<std::recursive_mutex> lock(send_mutex_);
        ok = DrainSendQueueLocked();
    }
    if (!ok && input_started_) {
        ESP_LOGW(TAG, "cancel voice input after audio send failed");
        if (audio_service_ != nullptr) {
            audio_service_->EnableVoiceProcessing(false);
        }
        {
            std::lock_guard<std::recursive_mutex> lock(send_mutex_);
            DropSendQueueLocked("send_failed");
        }
        ResetInputTracking();
        if (callbacks_.on_disconnected) {
            callbacks_.on_disconnected();
        }
    }
}

bool UsakiVoiceProtocolAdapter::DrainInputAudioBeforeEnd()
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    TickType_t started = xTaskGetTickCount();
    TickType_t max_wait = pdMS_TO_TICKS(kInputEndDrainMaxWaitMs);
    TickType_t poll_delay = pdMS_TO_TICKS(kInputEndDrainPollMs);
    if (poll_delay == 0) {
        poll_delay = 1;
    }

    while (true) {
        {
            std::lock_guard<std::recursive_mutex> lock(send_mutex_);
            if (!DrainSendQueueLocked()) {
                return false;
            }
            if (audio_service_ == nullptr || audio_service_->PendingInputAudioCount() == 0) {
                return server_ != nullptr && usaki_server_call_is_connected(server_);
            }
        }

        if (xTaskGetTickCount() - started >= max_wait) {
            break;
        }
        vTaskDelay(poll_delay);
    }

    std::lock_guard<std::recursive_mutex> lock(send_mutex_);
    if (!DrainSendQueueLocked()) {
        return false;
    }
    if (audio_service_ != nullptr && audio_service_->PendingInputAudioCount() > 0) {
        DropSendQueueLocked("input_end_drain_timeout");
    }
    return server_ != nullptr && usaki_server_call_is_connected(server_);
}

bool UsakiVoiceProtocolAdapter::DrainSendQueueLocked()
{
    if (spirit_privacy_muted()) { DropSendQueueLocked("privacy_mute"); return true; }
    if (server_ == nullptr || !usaki_server_call_is_connected(server_)) {
        return false;
    }

    if (!input_start_sent_) {
        size_t dropped = audio_service_ != nullptr
                             ? audio_service_->TrimSendQueueTo(kPreVadPrerollPackets)
                             : 0;
        if (dropped > 0) {
            ESP_LOGD(TAG,
                     "trim %u old pre-vad audio packet(s), keep=%u",
                     (unsigned)dropped,
                     (unsigned)kPreVadPrerollPackets);
        }
        return true;
    }

    while (true) {
        auto packet = audio_service_->PopPacketFromSendQueue();
        if (packet == nullptr) {
            break;
        }

        std::lock_guard<std::recursive_mutex> privacy_lock(spirit_privacy_gate());
        if (spirit_privacy_muted()) { DropSendQueueLocked("privacy_mute"); return true; }
        esp_err_t err = usaki_server_call_send_binary(server_,
                                                      packet->payload.data(),
                                                      packet->payload.size());
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "send audio packet failed: %s", esp_err_to_name(err));
            DropSendQueueLocked("send_failed");
            return false;
        }
    }
    return true;
}

int UsakiVoiceProtocolAdapter::DropSendQueueLocked(const char *reason)
{
    int dropped = audio_service_ != nullptr
                      ? (int)audio_service_->DiscardPendingInputAudio()
                      : 0;
    if (dropped > 0) {
        ESP_LOGW(TAG,
                 "drop %d pending input audio packet(s): %s",
                 dropped,
                 reason != nullptr ? reason : "unknown");
    }
    return dropped;
}

void UsakiVoiceProtocolAdapter::ResetInputTracking()
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    input_started_ = false;
    input_start_sent_ = false;
    awaiting_output_ = false;
    expected_output_request_id_[0] = '\0';
    input_started_at_ms_ = 0;
    vad_speech_seen_ = false;
    vad_speaking_ = false;
    vad_speech_started_at_ms_ = 0;
    vad_last_change_at_ms_ = 0;
}

void UsakiVoiceProtocolAdapter::FinishInputLocally(const char *reason)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    if (!input_started_) {
        return;
    }

    if (audio_service_ != nullptr) {
        audio_service_->EnableVoiceProcessing(false);
        std::lock_guard<std::recursive_mutex> lock(send_mutex_);
        DropSendQueueLocked(reason);
    }
    ResetInputTracking();
    ESP_LOGI(TAG, "voice input finished locally: %s", reason != nullptr ? reason : "server_output");
}

void UsakiVoiceProtocolAdapter::HandleConnected()
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    ESP_LOGI(TAG, "server connected");
    if (callbacks_.on_connected) {
        callbacks_.on_connected();
    }
}

void UsakiVoiceProtocolAdapter::HandleDisconnected()
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    ESP_LOGW(TAG, "server disconnected");
    ResetInputTracking();
    output_started_ = false;
    if (audio_service_ != nullptr) {
        audio_service_->EnableVoiceProcessing(false);
        {
            std::lock_guard<std::recursive_mutex> lock(send_mutex_);
            DropSendQueueLocked("disconnected");
        }
        audio_service_->ResetDecoder();
    }
    if (callbacks_.on_disconnected) {
        callbacks_.on_disconnected();
    }
}

void UsakiVoiceProtocolAdapter::HandleBinary(const uint8_t *data, size_t len)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    if (data == nullptr || len == 0) {
        return;
    }
    if (!output_started_) {
        TickType_t now = xTaskGetTickCount();
        if (last_output_not_started_drop_log_ == 0 ||
            now - last_output_not_started_drop_log_ >= pdMS_TO_TICKS(1000)) {
            ESP_LOGW(TAG, "drop output packet: output not started");
            last_output_not_started_drop_log_ = now;
        }
        return;
    }

    auto packet = std::make_unique<AudioStreamPacket>();
    packet->sample_rate = output_sample_rate_;
    packet->frame_duration = output_frame_duration_ms_;
    packet->payload.assign(data, data + len);
    if (!audio_service_->PushPacketToDecodeQueue(std::move(packet), false)) {
        ESP_LOGW(TAG, "drop output packet: decode queue full");
    }
}

void UsakiVoiceProtocolAdapter::HandleVoiceOutputStart(const usaki_protocol_server_message_t *message)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    const char *message_request_id = message != nullptr ? message->request_id : "";
    if (!awaiting_output_) {
        if (input_started_) {
            ESP_LOGW(TAG, "voice output start arrived while input is active; finishing input locally");
            FinishInputLocally("voice_output_start_while_input");
        } else {
            ESP_LOGW(TAG,
                     "ignore unexpected voice output start while %s",
                     input_started_ ? "input is active" : "not waiting for output");
            return;
        }
    }
    if (expected_output_request_id_[0] != '\0' &&
        (message_request_id == nullptr ||
         message_request_id[0] == '\0' ||
         strcmp(message_request_id, expected_output_request_id_) != 0)) {
        ESP_LOGW(TAG,
                 "ignore voice output start for stale request: got=%s expected=%s",
                 message_request_id != nullptr ? message_request_id : "",
                 expected_output_request_id_);
        return;
    }

    output_started_ = true;
    awaiting_output_ = false;
    expected_output_request_id_[0] = '\0';
    FinishInputLocally("voice_output_start");
    if (message != nullptr) {
        output_sample_rate_ = message->sample_rate > 0 ? message->sample_rate : 16000;
        output_frame_duration_ms_ = message->frame_duration_ms > 0
                                        ? message->frame_duration_ms
                                        : OPUS_FRAME_DURATION_MS;
        strlcpy(output_id_, message->output_id, sizeof(output_id_));
    }

    audio_service_->EnableVoiceProcessing(false);
    audio_service_->ResetDecoder();
    if (callbacks_.on_voice_output_start) {
        callbacks_.on_voice_output_start();
    }
    ESP_LOGI(TAG,
             "voice output started: sample_rate=%d frame_ms=%d",
             output_sample_rate_,
             output_frame_duration_ms_);
}

void UsakiVoiceProtocolAdapter::HandleVoiceOutputEnd(const usaki_protocol_server_message_t *message)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    const char *message_request_id = message != nullptr ? message->request_id : "";
    if (!output_started_ && !awaiting_output_) {
        if (input_started_) {
            ESP_LOGW(TAG, "voice output end arrived while input is active; finishing input locally");
            FinishInputLocally("voice_output_end_while_input");
            if (callbacks_.on_voice_output_end) {
                callbacks_.on_voice_output_end();
            }
            ESP_LOGI(TAG, "voice output ended");
            return;
        }
        ESP_LOGW(TAG, "ignore unexpected voice output end");
        return;
    }
    if (awaiting_output_ &&
        expected_output_request_id_[0] != '\0' &&
        (message_request_id == nullptr ||
         message_request_id[0] == '\0' ||
         strcmp(message_request_id, expected_output_request_id_) != 0)) {
        ESP_LOGW(TAG,
                 "ignore voice output end for stale request: got=%s expected=%s",
                 message_request_id != nullptr ? message_request_id : "",
                 expected_output_request_id_);
        return;
    }

    output_started_ = false;
    awaiting_output_ = false;
    output_id_[0] = '\0';
    expected_output_request_id_[0] = '\0';
    audio_service_->WaitForPlaybackQueueEmpty();
    audio_service_->FlushOutput();
    FinishInputLocally("voice_output_end");
    if (callbacks_.on_voice_output_end) {
        callbacks_.on_voice_output_end();
    }
    ESP_LOGI(TAG, "voice output ended");
}

void UsakiVoiceProtocolAdapter::HandleVoiceOutputCancel(const usaki_protocol_server_message_t *message)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    const char *message_request_id = message != nullptr ? message->request_id : "";
    if (!output_started_ && !awaiting_output_) {
        if (input_started_) {
            ESP_LOGW(TAG, "voice output cancel arrived while input is active; finishing input locally");
            FinishInputLocally("voice_output_cancel_while_input");
            if (callbacks_.on_voice_output_cancel) {
                callbacks_.on_voice_output_cancel();
            }
            ESP_LOGI(TAG, "voice output canceled");
            return;
        }
        ESP_LOGW(TAG, "ignore unexpected voice output cancel");
        return;
    }
    if (awaiting_output_ &&
        expected_output_request_id_[0] != '\0' &&
        (message_request_id == nullptr ||
         message_request_id[0] == '\0' ||
         strcmp(message_request_id, expected_output_request_id_) != 0)) {
        ESP_LOGW(TAG,
                 "ignore voice output cancel for stale request: got=%s expected=%s",
                 message_request_id != nullptr ? message_request_id : "",
                 expected_output_request_id_);
        return;
    }

    output_started_ = false;
    awaiting_output_ = false;
    output_id_[0] = '\0';
    expected_output_request_id_[0] = '\0';
    FinishInputLocally("voice_output_cancel");
    audio_service_->ResetDecoder();
    audio_service_->FlushOutput();
    if (callbacks_.on_voice_output_cancel) {
        callbacks_.on_voice_output_cancel();
    }
    ESP_LOGI(TAG, "voice output canceled");
}

void UsakiVoiceProtocolAdapter::HandleEmotionUpdate(const usaki_protocol_server_message_t *message)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    if (message == nullptr || message->emotion[0] == '\0') {
        ESP_LOGW(TAG, "ignore empty emotion update");
        return;
    }

    ESP_LOGI(TAG, "emotion update received: %s", message->emotion);
    if (callbacks_.on_emotion_update) {
        callbacks_.on_emotion_update(message);
    }
}

void UsakiVoiceProtocolAdapter::HandleEyeAnimation(const usaki_protocol_server_message_t *message)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    if (message == nullptr || message->name[0] == '\0') {
        ESP_LOGW(TAG, "ignore empty eye animation");
        return;
    }

    ESP_LOGI(TAG, "eye animation received: %s", message->name);
    if (callbacks_.on_eye_animation) {
        callbacks_.on_eye_animation(message);
    }
}

void UsakiVoiceProtocolAdapter::HandleBodyAction(const usaki_protocol_server_message_t *message)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    if (message == nullptr || message->body_action_count <= 0) {
        ESP_LOGW(TAG, "ignore empty body action");
        return;
    }

    ESP_LOGI(TAG, "body action received: count=%d", message->body_action_count);
    if (callbacks_.on_body_action) {
        callbacks_.on_body_action(message);
    }
}

void UsakiVoiceProtocolAdapter::HandleVadChange(bool speaking)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    if (spirit_privacy_muted()) return;
    ESP_LOGI(TAG, "device vad changed: %s", speaking ? "speech" : "silence");
    if (server_ == nullptr || !input_started_ || !usaki_server_call_is_connected(server_)) {
        return;
    }

    vad_speaking_ = speaking;
    vad_last_change_at_ms_ = usaki_protocol_now_ms();
    if (speaking) {
        vad_speech_seen_ = true;
        vad_speech_started_at_ms_ = vad_last_change_at_ms_;
        if (!input_start_sent_) {
            usaki_protocol_voice_input_start_t request = usaki_protocol_voice_input_start_default();
            request.request_id = request_id_;
            request.mode = "stream";
            request.vad.enabled = true;
            request.vad.source = "device_afe";

            esp_err_t err = usaki_server_call_send_voice_input_start(server_, &request);
            if (err != ESP_OK) {
                ESP_LOGW(TAG, "send voice.input.start after device vad failed: %s", esp_err_to_name(err));
                input_started_ = false;
                input_start_sent_ = false;
                audio_service_->EnableVoiceProcessing(false);
                DrainSendQueue();
                if (callbacks_.on_error) {
                    callbacks_.on_error(err, "send voice.input.start failed");
                }
                return;
            }

            input_started_at_ms_ = vad_last_change_at_ms_;
            input_start_sent_ = true;
            ESP_LOGI(TAG, "voice input started after device vad speech: %s", request_id_);
        }
    }

    if (!speaking && vad_speech_seen_) {
        const int64_t input_duration_ms = vad_last_change_at_ms_ - input_started_at_ms_;
        const int64_t speech_duration_ms = vad_speech_started_at_ms_ > 0
                                               ? vad_last_change_at_ms_ - vad_speech_started_at_ms_
                                               : 0;
        if (input_duration_ms < kDeviceVadMinInputMs ||
            speech_duration_ms < kDeviceVadMinSpeechMs) {
            ESP_LOGI(TAG,
                     "ignore short device vad silence: input_ms=%lld speech_ms=%lld",
                     (long long)input_duration_ms,
                     (long long)speech_duration_ms);
            return;
        }

        ESP_LOGI(TAG,
                 "device vad endpoint detected, ending input: input_ms=%lld speech_ms=%lld",
                 (long long)input_duration_ms,
                 (long long)speech_duration_ms);
        esp_err_t err = StopInput("vad_end");
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "stop input after device vad failed: %s", esp_err_to_name(err));
            if (callbacks_.on_disconnected) {
                callbacks_.on_disconnected();
            }
        }
    }
}

void UsakiVoiceProtocolAdapter::HandleWakeWordDetected(const std::string &wake_word)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    if (spirit_privacy_muted()) return;
    ESP_LOGI(TAG, "wake word detected: %s", wake_word.c_str());
    esp_err_t err = SendWakeWordDetected(wake_word.c_str(), true);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "send voice.wake.detected failed: %s", esp_err_to_name(err));
    }
    if (callbacks_.on_wake_word_detected) {
        callbacks_.on_wake_word_detected(wake_word.c_str());
    }
}

void UsakiVoiceProtocolAdapter::HandleError(esp_err_t err, const char *message)
{
    std::lock_guard<std::recursive_mutex> control_lock(send_mutex_);
    ESP_LOGW(TAG, "server call error: %s (%s)",
             message != nullptr ? message : "",
             esp_err_to_name(err));
    if (callbacks_.on_error) {
        callbacks_.on_error(err, message);
    }
}

void UsakiVoiceProtocolAdapter::OnConnected(void *user_ctx)
{
    static_cast<UsakiVoiceProtocolAdapter *>(user_ctx)->HandleConnected();
}

void UsakiVoiceProtocolAdapter::OnDisconnected(void *user_ctx)
{
    static_cast<UsakiVoiceProtocolAdapter *>(user_ctx)->HandleDisconnected();
}

void UsakiVoiceProtocolAdapter::OnBinary(const uint8_t *data, size_t len, void *user_ctx)
{
    static_cast<UsakiVoiceProtocolAdapter *>(user_ctx)->HandleBinary(data, len);
}

void UsakiVoiceProtocolAdapter::OnError(esp_err_t err, const char *message, void *user_ctx)
{
    static_cast<UsakiVoiceProtocolAdapter *>(user_ctx)->HandleError(err, message);
}

void UsakiVoiceProtocolAdapter::OnVoiceOutputStart(const usaki_protocol_server_message_t *message, void *user_ctx)
{
    static_cast<UsakiVoiceProtocolAdapter *>(user_ctx)->HandleVoiceOutputStart(message);
}

void UsakiVoiceProtocolAdapter::OnVoiceOutputEnd(const usaki_protocol_server_message_t *message, void *user_ctx)
{
    static_cast<UsakiVoiceProtocolAdapter *>(user_ctx)->HandleVoiceOutputEnd(message);
}

void UsakiVoiceProtocolAdapter::OnVoiceOutputCancel(const usaki_protocol_server_message_t *message, void *user_ctx)
{
    static_cast<UsakiVoiceProtocolAdapter *>(user_ctx)->HandleVoiceOutputCancel(message);
}

void UsakiVoiceProtocolAdapter::OnEmotionUpdate(const usaki_protocol_server_message_t *message, void *user_ctx)
{
    static_cast<UsakiVoiceProtocolAdapter *>(user_ctx)->HandleEmotionUpdate(message);
}

void UsakiVoiceProtocolAdapter::OnEyeAnimation(const usaki_protocol_server_message_t *message, void *user_ctx)
{
    static_cast<UsakiVoiceProtocolAdapter *>(user_ctx)->HandleEyeAnimation(message);
}

void UsakiVoiceProtocolAdapter::OnBodyAction(const usaki_protocol_server_message_t *message, void *user_ctx)
{
    static_cast<UsakiVoiceProtocolAdapter *>(user_ctx)->HandleBodyAction(message);
}
