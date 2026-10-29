#include "app/voice_runtime.h"

#include <cmath>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <memory>
#include <vector>

#include "audio/audio_service.h"
#include "app/spirit_privacy.h"
#include "audio/codecs/usaki_audio_codec.h"
#include "app/voice_protocol_adapter.h"
#include "board/usaki_board.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "sdkconfig.h"
#include "ui/usaki_eyes.h"

static const char *TAG = "voice_runtime";

typedef enum {
    VOICE_RUNTIME_EVENT_PROTOCOL_CONNECTED = 0,
    VOICE_RUNTIME_EVENT_PROTOCOL_DISCONNECTED,
    VOICE_RUNTIME_EVENT_VOICE_OUTPUT_START,
    VOICE_RUNTIME_EVENT_VOICE_OUTPUT_END,
    VOICE_RUNTIME_EVENT_VOICE_OUTPUT_CANCEL,
    VOICE_RUNTIME_EVENT_WAKE_WORD_DETECTED,
    VOICE_RUNTIME_EVENT_PROTOCOL_ERROR,
} voice_runtime_event_t;

static std::unique_ptr<UsakiAudioCodec> s_codec;
static std::unique_ptr<AudioService> s_audio_service;
static std::unique_ptr<UsakiVoiceProtocolAdapter> s_protocol_adapter;
static SemaphoreHandle_t s_state_lock;
static QueueHandle_t s_event_queue;
static usaki_voice_runtime_state_t s_state = USAKI_VOICE_RUNTIME_STATE_BOOTING;
static bool s_protocol_connected = false;
static std::atomic<bool> s_runtime_ready{false};

static constexpr float kPi = 3.14159265358979323846f;

static const char *state_name(usaki_voice_runtime_state_t state)
{
    switch (state) {
    case USAKI_VOICE_RUNTIME_STATE_BOOTING:
        return "booting";
    case USAKI_VOICE_RUNTIME_STATE_IDLE:
        return "idle";
    case USAKI_VOICE_RUNTIME_STATE_CONNECTING:
        return "connecting";
    case USAKI_VOICE_RUNTIME_STATE_LISTENING:
        return "listening";
    case USAKI_VOICE_RUNTIME_STATE_SPEAKING:
        return "speaking";
    case USAKI_VOICE_RUNTIME_STATE_INTERRUPTED:
        return "interrupted";
    case USAKI_VOICE_RUNTIME_STATE_ERROR:
        return "error";
    default:
        return "unknown";
    }
}

static void set_state(usaki_voice_runtime_state_t state)
{
    if (s_state_lock != nullptr) {
        xSemaphoreTake(s_state_lock, portMAX_DELAY);
    }
    if (s_state != state) {
        ESP_LOGI(TAG, "state: %s -> %s", state_name(s_state), state_name(state));
        s_state = state;
    }
    if (s_state_lock != nullptr) {
        xSemaphoreGive(s_state_lock);
    }

    switch (state) {
    case USAKI_VOICE_RUNTIME_STATE_CONNECTING:
        usaki_eyes_set_emotion(USAKI_EYE_EMOTION_SCAN);
        usaki_eyes_set_speaking(false);
        break;
    case USAKI_VOICE_RUNTIME_STATE_LISTENING:
        usaki_eyes_set_emotion(USAKI_EYE_EMOTION_IDLE);
        usaki_eyes_set_speaking(false);
        break;
    case USAKI_VOICE_RUNTIME_STATE_SPEAKING:
        usaki_eyes_set_emotion(USAKI_EYE_EMOTION_HAPPY);
        usaki_eyes_set_speaking(true);
        break;
    case USAKI_VOICE_RUNTIME_STATE_INTERRUPTED:
        usaki_eyes_set_emotion(USAKI_EYE_EMOTION_SURPRISED);
        usaki_eyes_set_speaking(false);
        break;
    case USAKI_VOICE_RUNTIME_STATE_ERROR:
        usaki_eyes_set_emotion(USAKI_EYE_EMOTION_ANGRY);
        usaki_eyes_set_speaking(false);
        break;
    case USAKI_VOICE_RUNTIME_STATE_IDLE:
    case USAKI_VOICE_RUNTIME_STATE_BOOTING:
    default:
        usaki_eyes_set_emotion(USAKI_EYE_EMOTION_IDLE);
        usaki_eyes_set_speaking(false);
        break;
    }
}

static void post_event(voice_runtime_event_t event)
{
    if (s_event_queue == nullptr) {
        ESP_LOGW(TAG, "drop event before queue ready: %d", (int)event);
        return;
    }

    BaseType_t ok = xQueueSend(s_event_queue, &event, 0);
    if (ok != pdPASS) {
        ESP_LOGW(TAG, "drop event because queue is full: %d", (int)event);
    }
}

static void on_protocol_connected()
{
    post_event(VOICE_RUNTIME_EVENT_PROTOCOL_CONNECTED);
}

static void on_protocol_disconnected()
{
    if (s_event_queue != nullptr) {
        xQueueReset(s_event_queue);
    }
    post_event(VOICE_RUNTIME_EVENT_PROTOCOL_DISCONNECTED);
}

static void on_voice_output_start()
{
    post_event(VOICE_RUNTIME_EVENT_VOICE_OUTPUT_START);
}

static void on_voice_output_end()
{
    post_event(VOICE_RUNTIME_EVENT_VOICE_OUTPUT_END);
}

static void on_voice_output_cancel()
{
    post_event(VOICE_RUNTIME_EVENT_VOICE_OUTPUT_CANCEL);
}

static void on_emotion_update(const usaki_protocol_server_message_t *message)
{
    if (message == nullptr || message->emotion[0] == '\0') {
        return;
    }
    const uint32_t duration_ms = message->duration_ms > 0 ? (uint32_t)message->duration_ms : 10000u;
    if (!usaki_eyes_set_emotion_name_for(message->emotion, duration_ms)) {
        ESP_LOGW(TAG, "failed to queue server eye emotion: %s", message->emotion);
    } else {
        ESP_LOGI(TAG, "queued server eye emotion: %s duration_ms=%u", message->emotion, (unsigned)duration_ms);
    }
}

static void on_eye_animation(const usaki_protocol_server_message_t *message)
{
    if (message == nullptr || message->name[0] == '\0') {
        return;
    }
    if (!usaki_eyes_play_animation_name(message->name)) {
        ESP_LOGW(TAG, "unsupported eye animation from server: %s", message->name);
    }
}

static void on_body_action(const usaki_protocol_server_message_t *message)
{
    (void)message;
    ESP_LOGW(TAG, "Usaki servo body.action unsupported on Spirit; ignored");
}

static void on_wake_word_detected(const char *wake_word)
{
    ESP_LOGI(TAG, "wake word trigger: %s", wake_word != nullptr ? wake_word : "");
    usaki_eyes_wake();
    post_event(VOICE_RUNTIME_EVENT_WAKE_WORD_DETECTED);
}

static void on_protocol_error(esp_err_t err, const char *message)
{
    ESP_LOGW(TAG, "protocol error: %s (%s)",
             message != nullptr ? message : "",
             esp_err_to_name(err));
    if (message != nullptr &&
        (strstr(message, "websocket") != nullptr ||
         strstr(message, "send voice.input") != nullptr ||
         strstr(message, "send binary") != nullptr)) {
        post_event(VOICE_RUNTIME_EVENT_PROTOCOL_DISCONNECTED);
        return;
    }
    post_event(VOICE_RUNTIME_EVENT_PROTOCOL_ERROR);
}

esp_err_t voice_runtime_init(void)
{
    if (s_audio_service != nullptr) {
        return ESP_OK;
    }

    if (s_state_lock == nullptr) {
        s_state_lock = xSemaphoreCreateMutex();
        if (s_state_lock == nullptr) {
            return ESP_ERR_NO_MEM;
        }
    }

    if (s_event_queue == nullptr) {
        s_event_queue = xQueueCreate(8, sizeof(voice_runtime_event_t));
        if (s_event_queue == nullptr) {
            return ESP_ERR_NO_MEM;
        }
    }

    set_state(USAKI_VOICE_RUNTIME_STATE_BOOTING);

    s_codec = std::make_unique<UsakiAudioCodec>();
    s_codec->Start();
    if (!s_codec->started()) { s_codec.reset(); return ESP_FAIL; }
    s_audio_service = std::make_unique<AudioService>();

    esp_err_t err = s_audio_service->Initialize(s_codec.get());
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "audio service init failed: %s", esp_err_to_name(err));
        s_audio_service.reset();
        s_codec.reset();
        return err;
    }

    err = s_audio_service->Start();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "audio service start failed: %s", esp_err_to_name(err));
        s_audio_service.reset();
        s_codec.reset();
        return err;
    }

    s_audio_service->EnableVoiceProcessing(false);

    s_protocol_adapter = std::make_unique<UsakiVoiceProtocolAdapter>(s_audio_service.get());
    UsakiVoiceProtocolAdapterCallbacks callbacks = {};
    callbacks.on_connected = on_protocol_connected;
    callbacks.on_disconnected = on_protocol_disconnected;
    callbacks.on_voice_output_start = on_voice_output_start;
    callbacks.on_voice_output_end = on_voice_output_end;
    callbacks.on_voice_output_cancel = on_voice_output_cancel;
    callbacks.on_emotion_update = on_emotion_update;
    callbacks.on_eye_animation = on_eye_animation;
    callbacks.on_body_action = on_body_action;
    callbacks.on_wake_word_detected = on_wake_word_detected;
    callbacks.on_error = on_protocol_error;
    s_protocol_adapter->SetCallbacks(callbacks);

    set_state(USAKI_VOICE_RUNTIME_STATE_CONNECTING);
    err = s_protocol_adapter->Start();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "voice protocol adapter start failed: %s", esp_err_to_name(err));
        s_protocol_adapter.reset();
        s_audio_service.reset();
        s_codec.reset();
        set_state(USAKI_VOICE_RUNTIME_STATE_ERROR);
        return err;
    }

    s_runtime_ready.store(true);
    ESP_LOGI(TAG, "voice runtime initialized with AudioService + protocol adapter");
    return ESP_OK;
}

static void handle_protocol_connected()
{
    s_protocol_connected = true;
    if (spirit_privacy_muted()) { set_state(USAKI_VOICE_RUNTIME_STATE_IDLE); return; }
#if CONFIG_USAKI_ENABLE_WAKE_WORD
    set_state(USAKI_VOICE_RUNTIME_STATE_IDLE);
    if (s_audio_service != nullptr) {
        esp_err_t err = s_audio_service->EnableWakeWordDetection(true);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "enable wake word failed: %s", esp_err_to_name(err));
            set_state(USAKI_VOICE_RUNTIME_STATE_ERROR);
        }
    }
#else
    // A reconnect never starts capture/upload on its own.
    set_state(USAKI_VOICE_RUNTIME_STATE_IDLE);
#endif
}

static void handle_start_listening_after_output(const char *source)
{
    if (spirit_privacy_muted()) { set_state(USAKI_VOICE_RUNTIME_STATE_IDLE); return; }
    if (!s_protocol_connected) {
        ESP_LOGW(TAG, "skip start listening after %s because protocol is disconnected", source);
        return;
    }

    esp_err_t err = voice_runtime_start_listening();
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "start listening after %s failed: %s", source, esp_err_to_name(err));
        set_state(USAKI_VOICE_RUNTIME_STATE_ERROR);
    }
}

static void handle_runtime_event(voice_runtime_event_t event)
{
    switch (event) {
    case VOICE_RUNTIME_EVENT_PROTOCOL_CONNECTED:
        handle_protocol_connected();
        break;
    case VOICE_RUNTIME_EVENT_PROTOCOL_DISCONNECTED:
        s_protocol_connected = false;
        set_state(USAKI_VOICE_RUNTIME_STATE_CONNECTING);
        break;
    case VOICE_RUNTIME_EVENT_VOICE_OUTPUT_START:
        set_state(USAKI_VOICE_RUNTIME_STATE_SPEAKING);
        break;
    case VOICE_RUNTIME_EVENT_VOICE_OUTPUT_END:
        set_state(USAKI_VOICE_RUNTIME_STATE_IDLE);
        break;
    case VOICE_RUNTIME_EVENT_VOICE_OUTPUT_CANCEL:
        set_state(USAKI_VOICE_RUNTIME_STATE_IDLE);
        break;
    case VOICE_RUNTIME_EVENT_WAKE_WORD_DETECTED:
        handle_start_listening_after_output("wake word");
        break;
    case VOICE_RUNTIME_EVENT_PROTOCOL_ERROR:
        set_state(USAKI_VOICE_RUNTIME_STATE_ERROR);
        break;
    default:
        ESP_LOGW(TAG, "unknown event: %d", (int)event);
        break;
    }
}

void voice_runtime_run(void)
{
    ESP_LOGI(TAG, "voice runtime running");

    while (true) {
        voice_runtime_event_t event;
        if (xQueueReceive(s_event_queue, &event, portMAX_DELAY) == pdPASS) {
            handle_runtime_event(event);
        }
    }
}

esp_err_t voice_runtime_start_listening(void)
{
    if (!s_runtime_ready.load()) return ESP_ERR_INVALID_STATE;
    if (spirit_privacy_muted()) return ESP_ERR_INVALID_STATE;
    if (s_protocol_adapter == nullptr) {
        return ESP_ERR_INVALID_STATE;
    }
#if CONFIG_USAKI_ENABLE_WAKE_WORD
    if (s_audio_service != nullptr) {
        (void)s_audio_service->EnableWakeWordDetection(false);
    }
#endif
    esp_err_t err = s_protocol_adapter->StartInput();
    if (err == ESP_OK) {
        set_state(USAKI_VOICE_RUNTIME_STATE_LISTENING);
    }
    return err;
}

esp_err_t voice_runtime_stop_listening(void)
{
    if (!s_runtime_ready.load()) return ESP_ERR_INVALID_STATE;
    if (s_protocol_adapter == nullptr) {
        return ESP_ERR_INVALID_STATE;
    }
    esp_err_t err = s_protocol_adapter->StopInput("manual");
    if (err == ESP_OK) {
        set_state(USAKI_VOICE_RUNTIME_STATE_IDLE);
#if CONFIG_USAKI_ENABLE_WAKE_WORD
        if (s_audio_service != nullptr) {
            (void)s_audio_service->EnableWakeWordDetection(true);
        }
#endif
    }
    return err;
}

esp_err_t voice_runtime_interrupt(void)
{
    if (!s_runtime_ready.load()) return ESP_ERR_INVALID_STATE;
    if (s_protocol_adapter == nullptr) {
        return ESP_ERR_INVALID_STATE;
    }
    set_state(USAKI_VOICE_RUNTIME_STATE_INTERRUPTED);
    return s_protocol_adapter->InterruptOutput("user_interrupt");
}

esp_err_t voice_runtime_play_sleepy_sound(void)
{
    if (!s_runtime_ready.load()) return ESP_ERR_INVALID_STATE;
    if (s_audio_service == nullptr || s_codec == nullptr) {
        return ESP_ERR_INVALID_STATE;
    }

    const int sample_rate = s_codec->output_sample_rate() > 0 ? s_codec->output_sample_rate() : 16000;
    const int duration_ms = 720;
    const int sample_count = sample_rate * duration_ms / 1000;
    std::vector<int16_t> pcm(sample_count);

    float phase = 0.0f;
    for (int i = 0; i < sample_count; ++i) {
        const float u = sample_count > 1 ? static_cast<float>(i) / static_cast<float>(sample_count - 1) : 0.0f;
        const float t = static_cast<float>(i) / static_cast<float>(sample_rate);
        const float attack = u < 0.08f ? u / 0.08f : 1.0f;
        const float release = u > 0.72f ? (1.0f - u) / 0.28f : 1.0f;
        const float env = std::fmax(0.0f, std::fmin(attack, release));
        const float freq = 520.0f - 285.0f * u + 18.0f * std::sin(2.0f * kPi * 2.8f * u);
        phase += 2.0f * kPi * freq / static_cast<float>(sample_rate);

        const float yawn = std::sin(phase) * 0.76f +
                           std::sin(phase * 0.5f + 0.9f) * 0.22f +
                           std::sin(2.0f * kPi * 6.0f * t) * 0.035f;
        const int32_t sample = static_cast<int32_t>(yawn * env * 5200.0f);
        pcm[i] = static_cast<int16_t>(sample);
    }

    if (!s_audio_service->PlayLocalPcm(std::move(pcm), false)) {
        return ESP_FAIL;
    }
    return ESP_OK;
}

usaki_voice_runtime_state_t voice_runtime_get_state(void)
{
    if (!s_runtime_ready.load()) return USAKI_VOICE_RUNTIME_STATE_BOOTING;
    usaki_voice_runtime_state_t state;
    if (s_state_lock != nullptr) {
        xSemaphoreTake(s_state_lock, portMAX_DELAY);
    }
    state = s_state;
    if (s_state_lock != nullptr) {
        xSemaphoreGive(s_state_lock);
    }
    return state;
}

esp_err_t voice_runtime_set_privacy_mute(bool mute)
{
    esp_err_t err = spirit_privacy_set_muted(mute);
    if (!s_runtime_ready.load()) return err;
    // Setter fails closed on persistence errors.
    if (spirit_privacy_muted()) {
        if (s_codec) s_codec->EnableInput(false);
        if (s_audio_service) {
            s_audio_service->EnableVoiceProcessing(false);
            (void)s_audio_service->EnableWakeWordDetection(false);
            s_audio_service->DiscardPendingInputAudio();
        }
        if (s_protocol_adapter) (void)s_protocol_adapter->StopInput("privacy_mute");
        set_state(USAKI_VOICE_RUNTIME_STATE_IDLE);
    } else if (s_codec) {
        s_codec->EnableInput(false);
        // Unmuting does not automatically start an upload; short-press to talk.
    }
    return err;
}
