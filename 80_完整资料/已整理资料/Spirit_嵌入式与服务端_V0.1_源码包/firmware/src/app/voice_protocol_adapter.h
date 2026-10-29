#pragma once

#include <cstdint>
#include <atomic>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include <functional>
#include <mutex>
#include <string>

#include "app/protocol.h"
#include "app/server_call.h"
#include "audio/audio_service.h"
#include "esp_err.h"

struct UsakiVoiceProtocolAdapterCallbacks {
    std::function<void(void)> on_connected;
    std::function<void(void)> on_disconnected;
    std::function<void(void)> on_voice_output_start;
    std::function<void(void)> on_voice_output_end;
    std::function<void(void)> on_voice_output_cancel;
    std::function<void(const usaki_protocol_server_message_t *message)> on_emotion_update;
    std::function<void(const usaki_protocol_server_message_t *message)> on_eye_animation;
    std::function<void(const usaki_protocol_server_message_t *message)> on_body_action;
    std::function<void(const char *wake_word)> on_wake_word_detected;
    std::function<void(esp_err_t err, const char *message)> on_error;
};

class UsakiVoiceProtocolAdapter {
public:
    explicit UsakiVoiceProtocolAdapter(AudioService *audio_service);
    ~UsakiVoiceProtocolAdapter();

    esp_err_t Start();
    void Stop();
    void SetCallbacks(const UsakiVoiceProtocolAdapterCallbacks &callbacks);

    esp_err_t StartInput();
    esp_err_t StopInput(const char *reason);
    esp_err_t InterruptOutput(const char *reason);
    esp_err_t SendWakeWordDetected(const char *wake_word, bool will_start_input);

private:
    AudioService *audio_service_ = nullptr;
    UsakiVoiceProtocolAdapterCallbacks callbacks_;
    usaki_server_call_handle_t server_ = nullptr;
    TaskHandle_t send_task_handle_ = nullptr;
    SemaphoreHandle_t send_exited_ = nullptr;
    std::atomic<bool> send_stopping_{false};
    bool input_started_ = false;
    bool input_start_sent_ = false;
    bool output_started_ = false;
    bool awaiting_output_ = false;
    TickType_t last_output_not_started_drop_log_ = 0;
    bool vad_speech_seen_ = false;
    bool vad_speaking_ = false;
    int64_t vad_speech_started_at_ms_ = 0;
    int64_t vad_last_change_at_ms_ = 0;
    int output_sample_rate_ = 16000;
    int output_frame_duration_ms_ = OPUS_FRAME_DURATION_MS;
    // Single recursive control/send lock serializes turn state across runtime,
    // WebSocket and send tasks. Recursive because callbacks call turn helpers.
    std::recursive_mutex send_mutex_;
    char request_id_[40] = {0};
    char expected_output_request_id_[40] = {0};
    char output_id_[64] = {0};
    int64_t input_started_at_ms_ = 0;

    static void SendTaskEntry(void *arg);
    void SendTask();
    void NotifySendTask();
    void DrainSendQueue();
    bool DrainInputAudioBeforeEnd();
    bool DrainSendQueueLocked();
    int DropSendQueueLocked(const char *reason);
    void ResetInputTracking();
    void FinishInputLocally(const char *reason);
    void HandleConnected();
    void HandleDisconnected();
    void HandleBinary(const uint8_t *data, size_t len);
    void HandleVoiceOutputStart(const usaki_protocol_server_message_t *message);
    void HandleVoiceOutputEnd(const usaki_protocol_server_message_t *message);
    void HandleVoiceOutputCancel(const usaki_protocol_server_message_t *message);
    void HandleEmotionUpdate(const usaki_protocol_server_message_t *message);
    void HandleEyeAnimation(const usaki_protocol_server_message_t *message);
    void HandleBodyAction(const usaki_protocol_server_message_t *message);
    void HandleVadChange(bool speaking);
    void HandleWakeWordDetected(const std::string &wake_word);
    void HandleError(esp_err_t err, const char *message);

    static void OnConnected(void *user_ctx);
    static void OnDisconnected(void *user_ctx);
    static void OnBinary(const uint8_t *data, size_t len, void *user_ctx);
    static void OnError(esp_err_t err, const char *message, void *user_ctx);
    static void OnVoiceOutputStart(const usaki_protocol_server_message_t *message, void *user_ctx);
    static void OnVoiceOutputEnd(const usaki_protocol_server_message_t *message, void *user_ctx);
    static void OnVoiceOutputCancel(const usaki_protocol_server_message_t *message, void *user_ctx);
    static void OnEmotionUpdate(const usaki_protocol_server_message_t *message, void *user_ctx);
    static void OnEyeAnimation(const usaki_protocol_server_message_t *message, void *user_ctx);
    static void OnBodyAction(const usaki_protocol_server_message_t *message, void *user_ctx);
};
