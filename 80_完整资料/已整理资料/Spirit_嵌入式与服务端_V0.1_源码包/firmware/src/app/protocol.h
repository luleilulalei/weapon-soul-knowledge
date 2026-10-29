#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define USAKI_PROTOCOL_VERSION "1.1"
#define USAKI_PROTOCOL_AUDIO_CODEC_OPUS "opus"
#define USAKI_PROTOCOL_AUDIO_FRAME_DURATION_MS 60
#define USAKI_PROTOCOL_MAX_BODY_ACTIONS 6
#define USAKI_PROTOCOL_MAX_MOTION_SERVOS 8

typedef enum
{
    USAKI_PROTOCOL_SERVER_MESSAGE_UNKNOWN = 0,
    USAKI_PROTOCOL_SERVER_MESSAGE_VOICE_OUTPUT_START,
    USAKI_PROTOCOL_SERVER_MESSAGE_VOICE_OUTPUT_END,
    USAKI_PROTOCOL_SERVER_MESSAGE_VOICE_OUTPUT_CANCEL,
    USAKI_PROTOCOL_SERVER_MESSAGE_EMOTION_UPDATE,
    USAKI_PROTOCOL_SERVER_MESSAGE_EYE_ANIMATION,
    USAKI_PROTOCOL_SERVER_MESSAGE_BODY_ACTION,
    USAKI_PROTOCOL_SERVER_MESSAGE_MOTION_SERVO_BATCH,
    USAKI_PROTOCOL_SERVER_MESSAGE_NOTIFICATION_PUSH,
    USAKI_PROTOCOL_SERVER_MESSAGE_ERROR,
} usaki_protocol_server_message_type_t;

typedef struct
{
    char part[32];
    char action[32];
    int angle;
    int count;
    int duration_ms;
} usaki_protocol_body_action_item_t;

typedef struct
{
    char part[32];
    char kind[16];
    char op[16];
    char direction[8];
    char speed[8];
    int channel;
    int pulse_us;
    int angle;
    int duration_ms;
    int ttl_ms;
} usaki_protocol_motion_servo_item_t;

typedef struct
{
    char id[40];
    usaki_protocol_server_message_type_t type;
    char type_name[32];
    char device_id[64];
    int64_t timestamp;
    int seq;
    bool success;
    int code;
    bool retryable;
    char ref_id[40];
    char message[128];
    char request_id[64];
    char output_id[64];
    char command_id[64];
    char source[32];
    char name[32];
    char emotion[32];
    char reason[32];
    int duration_ms;
    char codec[16];
    int sample_rate;
    int channels;
    int sample_bits;
    int frame_duration_ms;
    float intensity;
    bool loop;
    bool interrupt;
    int priority;
    int ttl_ms;
    int body_action_count;
    usaki_protocol_body_action_item_t body_actions[USAKI_PROTOCOL_MAX_BODY_ACTIONS];
    int motion_servo_count;
    usaki_protocol_motion_servo_item_t motion_servos[USAKI_PROTOCOL_MAX_MOTION_SERVOS];
} usaki_protocol_server_message_t;

typedef struct
{
    const char *message_id;
    const char *device_id;
    int seq;
} usaki_protocol_message_header_t;

typedef struct
{
    bool audio_input;
    bool audio_output;
    bool touch;
    bool screen;
    bool body;
} usaki_protocol_capabilities_t;

typedef struct
{
    const char *device_id;
    const char *firmware_version;
    const char *hardware_version;
    const char *protocol_version;
    usaki_protocol_capabilities_t capabilities;
} usaki_protocol_device_connect_request_t;

typedef struct
{
    char token[128];
    int config_version;
} usaki_protocol_device_connect_response_t;

typedef struct
{
    bool enabled;
    const char *source;
} usaki_protocol_vad_t;

typedef struct
{
    usaki_protocol_message_header_t header;
    const char *request_id;
    const char *codec;
    int sample_rate;
    int channels;
    int sample_bits;
    int frame_duration_ms;
    const char *mode;
    usaki_protocol_vad_t vad;
} usaki_protocol_voice_input_start_t;

typedef struct
{
    usaki_protocol_message_header_t header;
    const char *request_id;
    const char *reason;
    int duration_ms;
} usaki_protocol_voice_input_end_t;

typedef struct
{
    usaki_protocol_message_header_t header;
    const char *request_id;
    const char *reason;
} usaki_protocol_voice_input_cancel_t;

typedef struct
{
    usaki_protocol_message_header_t header;
    const char *wake_word;
    float confidence;
    const char *input_mode;
    bool will_start_input;
} usaki_protocol_voice_wake_detected_t;

typedef struct
{
    usaki_protocol_message_header_t header;
    const char *output_id;
    const char *reason;
} usaki_protocol_voice_interrupt_t;

typedef struct
{
    usaki_protocol_message_header_t header;
    const char *area;
    const char *event;
    int value;
    int duration_ms;
} usaki_protocol_touch_event_t;

typedef struct
{
    float x;
    float y;
    float z;
} usaki_protocol_imu_t;

typedef struct
{
    usaki_protocol_message_header_t header;
    usaki_protocol_imu_t imu;
    float light;
    float distance;
} usaki_protocol_sensor_update_t;

typedef struct
{
    usaki_protocol_message_header_t header;
    const char *ref_id;
    int code;
    const char *message;
    bool retryable;
} usaki_protocol_error_t;

int64_t usaki_protocol_now_ms(void);

usaki_protocol_device_connect_request_t usaki_protocol_device_connect_request_default(void);

usaki_protocol_voice_input_start_t usaki_protocol_voice_input_start_default(void);

usaki_protocol_voice_input_end_t usaki_protocol_voice_input_end_default(void);

usaki_protocol_voice_input_cancel_t usaki_protocol_voice_input_cancel_default(void);

usaki_protocol_voice_wake_detected_t usaki_protocol_voice_wake_detected_default(void);

usaki_protocol_voice_interrupt_t usaki_protocol_voice_interrupt_default(void);

usaki_protocol_touch_event_t usaki_protocol_touch_event_default(void);

usaki_protocol_sensor_update_t usaki_protocol_sensor_update_default(void);

usaki_protocol_error_t usaki_protocol_error_default(void);

esp_err_t usaki_protocol_build_device_connect_request(
    const usaki_protocol_device_connect_request_t *request,
    char *buffer,
    size_t buffer_len);

esp_err_t usaki_protocol_parse_device_connect_response(
    const char *json,
    size_t json_len,
    usaki_protocol_device_connect_response_t *out);

esp_err_t usaki_protocol_build_voice_input_start(const usaki_protocol_voice_input_start_t *request,
                                                 char *buffer,
                                                 size_t buffer_len);

esp_err_t usaki_protocol_build_voice_input_end(const usaki_protocol_voice_input_end_t *request,
                                               char *buffer,
                                               size_t buffer_len);

esp_err_t usaki_protocol_build_voice_input_cancel(const usaki_protocol_voice_input_cancel_t *request,
                                                  char *buffer,
                                                  size_t buffer_len);

esp_err_t usaki_protocol_build_voice_wake_detected(const usaki_protocol_voice_wake_detected_t *request,
                                                   char *buffer,
                                                   size_t buffer_len);

esp_err_t usaki_protocol_build_voice_interrupt(const usaki_protocol_voice_interrupt_t *request,
                                               char *buffer,
                                               size_t buffer_len);

esp_err_t usaki_protocol_build_touch_event(const usaki_protocol_touch_event_t *request,
                                           char *buffer,
                                           size_t buffer_len);

esp_err_t usaki_protocol_build_sensor_update(const usaki_protocol_sensor_update_t *request,
                                             char *buffer,
                                             size_t buffer_len);

esp_err_t usaki_protocol_build_error(const usaki_protocol_error_t *request,
                                     char *buffer,
                                     size_t buffer_len);

esp_err_t usaki_protocol_parse_server_message(const char *json,
                                              size_t json_len,
                                              usaki_protocol_server_message_t *out);

#ifdef __cplusplus
}
#endif
