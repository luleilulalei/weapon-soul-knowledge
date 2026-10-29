#include "app/protocol.h"

#include <string.h>

#include "cJSON.h"
#include "esp_check.h"
#include "esp_timer.h"

static const char *TAG = "usaki_protocol";

int64_t usaki_protocol_now_ms(void)
{
    return esp_timer_get_time() / 1000;
}

static const char *safe_string(const char *value)
{
    return value != NULL ? value : "";
}

static const char *string_or_default(const char *value, const char *default_value)
{
    return value != NULL ? value : default_value;
}

static void copy_json_string(cJSON *object, const char *name, char *buffer, size_t buffer_len)
{
    cJSON *item = cJSON_GetObjectItemCaseSensitive(object, name);
    if (buffer_len == 0)
    {
        return;
    }
    buffer[0] = '\0';
    if (cJSON_IsString(item) && item->valuestring != NULL)
    {
        strlcpy(buffer, item->valuestring, buffer_len);
    }
}

static int json_int(cJSON *object, const char *name, int default_value)
{
    cJSON *item = cJSON_GetObjectItemCaseSensitive(object, name);
    return cJSON_IsNumber(item) ? item->valueint : default_value;
}

static double json_double(cJSON *object, const char *name, double default_value)
{
    cJSON *item = cJSON_GetObjectItemCaseSensitive(object, name);
    return cJSON_IsNumber(item) ? item->valuedouble : default_value;
}

static bool json_bool(cJSON *object, const char *name, bool default_value)
{
    cJSON *item = cJSON_GetObjectItemCaseSensitive(object, name);
    return cJSON_IsBool(item) ? cJSON_IsTrue(item) : default_value;
}

static void copy_body_action_item(cJSON *object, usaki_protocol_body_action_item_t *out)
{
    if (!cJSON_IsObject(object) || out == NULL)
    {
        return;
    }

    copy_json_string(object, "part", out->part, sizeof(out->part));
    copy_json_string(object, "action", out->action, sizeof(out->action));
    out->angle = json_int(object, "angle", 0);
    out->count = json_int(object, "count", 0);
    out->duration_ms = json_int(object, "duration_ms", 0);
}

static void parse_body_actions(cJSON *data, usaki_protocol_server_message_t *out)
{
    if (out == NULL || !cJSON_IsObject(data))
    {
        return;
    }

    cJSON *actions = cJSON_GetObjectItemCaseSensitive(data, "actions");
    if (cJSON_IsArray(actions))
    {
        int count = cJSON_GetArraySize(actions);
        if (count > USAKI_PROTOCOL_MAX_BODY_ACTIONS)
        {
            count = USAKI_PROTOCOL_MAX_BODY_ACTIONS;
        }
        for (int i = 0; i < count; ++i)
        {
            copy_body_action_item(cJSON_GetArrayItem(actions, i), &out->body_actions[i]);
        }
        out->body_action_count = count;
        return;
    }

    copy_body_action_item(data, &out->body_actions[0]);
    if (out->body_actions[0].part[0] != '\0' || out->body_actions[0].action[0] != '\0')
    {
        out->body_action_count = 1;
    }
}

static void copy_motion_servo_item(cJSON *object, usaki_protocol_motion_servo_item_t *out)
{
    if (!cJSON_IsObject(object) || out == NULL)
    {
        return;
    }

    copy_json_string(object, "part", out->part, sizeof(out->part));
    copy_json_string(object, "kind", out->kind, sizeof(out->kind));
    copy_json_string(object, "op", out->op, sizeof(out->op));
    copy_json_string(object, "direction", out->direction, sizeof(out->direction));
    copy_json_string(object, "speed", out->speed, sizeof(out->speed));
    out->channel = json_int(object, "channel", -1);
    out->pulse_us = json_int(object, "pulse_us", 0);
    out->angle = json_int(object, "angle", 0);
    out->duration_ms = json_int(object, "duration_ms", 0);
    out->ttl_ms = json_int(object, "ttl_ms", 0);
}

static void parse_motion_servo_batch(cJSON *data, usaki_protocol_server_message_t *out)
{
    if (out == NULL || !cJSON_IsObject(data))
    {
        return;
    }

    cJSON *servos = cJSON_GetObjectItemCaseSensitive(data, "servos");
    if (!cJSON_IsArray(servos))
    {
        return;
    }

    int count = cJSON_GetArraySize(servos);
    if (count > USAKI_PROTOCOL_MAX_MOTION_SERVOS)
    {
        count = USAKI_PROTOCOL_MAX_MOTION_SERVOS;
    }
    for (int i = 0; i < count; ++i)
    {
        copy_motion_servo_item(cJSON_GetArrayItem(servos, i), &out->motion_servos[i]);
    }
    out->motion_servo_count = count;
}

static esp_err_t print_json_to_buffer(cJSON *root, char *buffer, size_t buffer_len)
{
    ESP_RETURN_ON_FALSE(buffer != NULL, ESP_ERR_INVALID_ARG, TAG, "buffer is null");
    ESP_RETURN_ON_FALSE(buffer_len > 0, ESP_ERR_INVALID_ARG, TAG, "buffer_len is zero");

    if (!cJSON_PrintPreallocated(root, buffer, (int)buffer_len, false))
    {
        buffer[0] = '\0';
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

static cJSON *create_message_root(const usaki_protocol_message_header_t *header,
                                  const char *type,
                                  cJSON **data_out)
{
    cJSON *root = cJSON_CreateObject();
    cJSON *data = cJSON_CreateObject();
    if (root == NULL || data == NULL)
    {
        cJSON_Delete(root);
        cJSON_Delete(data);
        return NULL;
    }

    cJSON_AddStringToObject(root, "id", safe_string(header->message_id));
    cJSON_AddStringToObject(root, "type", type);
    cJSON_AddStringToObject(root, "device_id", safe_string(header->device_id));
    cJSON_AddNumberToObject(root, "timestamp", (double)usaki_protocol_now_ms());
    cJSON_AddNumberToObject(root, "seq", header->seq);
    cJSON_AddItemToObject(root, "data", data);
    *data_out = data;
    return root;
}

static esp_err_t finish_message(cJSON *root, char *buffer, size_t buffer_len)
{
    if (root == NULL)
    {
        return ESP_ERR_NO_MEM;
    }
    esp_err_t err = print_json_to_buffer(root, buffer, buffer_len);
    cJSON_Delete(root);
    return err;
}

usaki_protocol_device_connect_request_t usaki_protocol_device_connect_request_default(void)
{
    return (usaki_protocol_device_connect_request_t){
        .protocol_version = USAKI_PROTOCOL_VERSION,
        .capabilities = {
            .audio_input = true,
            .audio_output = true,
            .touch = true,
            .screen = true,
            .body = false,
        },
    };
}

usaki_protocol_voice_input_start_t usaki_protocol_voice_input_start_default(void)
{
    return (usaki_protocol_voice_input_start_t){
        .codec = USAKI_PROTOCOL_AUDIO_CODEC_OPUS,
        .sample_rate = 16000,
        .channels = 1,
        .sample_bits = 16,
        .frame_duration_ms = USAKI_PROTOCOL_AUDIO_FRAME_DURATION_MS,
        .mode = "stream",
        .vad = {
            .enabled = true,
            .source = "device",
        },
    };
}

usaki_protocol_voice_input_end_t usaki_protocol_voice_input_end_default(void)
{
    return (usaki_protocol_voice_input_end_t){
        .reason = "vad_end",
    };
}

usaki_protocol_voice_input_cancel_t usaki_protocol_voice_input_cancel_default(void)
{
    return (usaki_protocol_voice_input_cancel_t){
        .reason = "user_cancel",
    };
}

usaki_protocol_voice_wake_detected_t usaki_protocol_voice_wake_detected_default(void)
{
    return (usaki_protocol_voice_wake_detected_t){
        .confidence = 0.0f,
        .input_mode = "wake_word",
        .will_start_input = true,
    };
}

usaki_protocol_voice_interrupt_t usaki_protocol_voice_interrupt_default(void)
{
    return (usaki_protocol_voice_interrupt_t){
        .reason = "user_speaking",
    };
}

usaki_protocol_touch_event_t usaki_protocol_touch_event_default(void)
{
    return (usaki_protocol_touch_event_t){0};
}

usaki_protocol_sensor_update_t usaki_protocol_sensor_update_default(void)
{
    return (usaki_protocol_sensor_update_t){0};
}

usaki_protocol_error_t usaki_protocol_error_default(void)
{
    return (usaki_protocol_error_t){0};
}

esp_err_t usaki_protocol_build_device_connect_request(
    const usaki_protocol_device_connect_request_t *request,
    char *buffer,
    size_t buffer_len)
{
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");

    cJSON *root = cJSON_CreateObject();
    if (root == NULL)
    {
        return ESP_ERR_NO_MEM;
    }

    cJSON_AddStringToObject(root, "device_id", safe_string(request->device_id));
    cJSON_AddStringToObject(root, "firmware_version", safe_string(request->firmware_version));
    cJSON_AddStringToObject(root, "hardware_version", safe_string(request->hardware_version));
    cJSON_AddStringToObject(root,
                            "protocol_version",
                            string_or_default(request->protocol_version, USAKI_PROTOCOL_VERSION));

    cJSON *capabilities = cJSON_CreateObject();
    if (capabilities == NULL)
    {
        cJSON_Delete(root);
        return ESP_ERR_NO_MEM;
    }
    cJSON_AddBoolToObject(capabilities, "audio_input", request->capabilities.audio_input);
    cJSON_AddBoolToObject(capabilities, "audio_output", request->capabilities.audio_output);
    cJSON_AddBoolToObject(capabilities, "touch", request->capabilities.touch);
    cJSON_AddBoolToObject(capabilities, "screen", request->capabilities.screen);
    cJSON_AddBoolToObject(capabilities, "body", request->capabilities.body);
    cJSON_AddItemToObject(root, "capabilities", capabilities);
    return finish_message(root, buffer, buffer_len);
}

esp_err_t usaki_protocol_parse_device_connect_response(
    const char *json,
    size_t json_len,
    usaki_protocol_device_connect_response_t *out)
{
    ESP_RETURN_ON_FALSE(json != NULL, ESP_ERR_INVALID_ARG, TAG, "json is null");
    ESP_RETURN_ON_FALSE(out != NULL, ESP_ERR_INVALID_ARG, TAG, "out is null");

    cJSON *root = cJSON_ParseWithLength(json, json_len);
    ESP_RETURN_ON_FALSE(root != NULL, ESP_ERR_INVALID_RESPONSE, TAG, "invalid json");

    memset(out, 0, sizeof(*out));
    cJSON *data = cJSON_GetObjectItemCaseSensitive(root, "data");
    if (!cJSON_IsObject(data))
    {
        cJSON_Delete(root);
        return ESP_ERR_INVALID_RESPONSE;
    }

    copy_json_string(data, "token", out->token, sizeof(out->token));
    out->config_version = json_int(data, "config_version", 0);
    cJSON_Delete(root);

    return out->token[0] != '\0' ? ESP_OK : ESP_ERR_INVALID_RESPONSE;
}

esp_err_t usaki_protocol_build_voice_input_start(const usaki_protocol_voice_input_start_t *request,
                                                 char *buffer,
                                                 size_t buffer_len)
{
    cJSON *data = NULL;
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");

    cJSON *root = create_message_root(&request->header, "voice.input.start", &data);
    if (root == NULL)
    {
        return ESP_ERR_NO_MEM;
    }

    cJSON_AddStringToObject(data, "request_id", safe_string(request->request_id));
    cJSON_AddStringToObject(data, "codec", string_or_default(request->codec, USAKI_PROTOCOL_AUDIO_CODEC_OPUS));
    cJSON_AddNumberToObject(data, "sample_rate", request->sample_rate);
    cJSON_AddNumberToObject(data, "channels", request->channels);
    cJSON_AddNumberToObject(data, "sample_bits", request->sample_bits);
    cJSON_AddNumberToObject(data,
                            "frame_duration_ms",
                            request->frame_duration_ms > 0 ? request->frame_duration_ms : USAKI_PROTOCOL_AUDIO_FRAME_DURATION_MS);
    cJSON_AddStringToObject(data, "mode", string_or_default(request->mode, "stream"));

    cJSON *vad = cJSON_CreateObject();
    if (vad == NULL)
    {
        cJSON_Delete(root);
        return ESP_ERR_NO_MEM;
    }
    cJSON_AddBoolToObject(vad, "enabled", request->vad.enabled);
    cJSON_AddStringToObject(vad, "source", string_or_default(request->vad.source, "device"));
    cJSON_AddItemToObject(data, "vad", vad);
    return finish_message(root, buffer, buffer_len);
}

esp_err_t usaki_protocol_build_voice_input_end(const usaki_protocol_voice_input_end_t *request,
                                               char *buffer,
                                               size_t buffer_len)
{
    cJSON *data = NULL;
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");

    cJSON *root = create_message_root(&request->header, "voice.input.end", &data);
    if (root == NULL)
    {
        return ESP_ERR_NO_MEM;
    }
    cJSON_AddStringToObject(data, "request_id", safe_string(request->request_id));
    cJSON_AddStringToObject(data, "reason", string_or_default(request->reason, "vad_end"));
    cJSON_AddNumberToObject(data, "duration_ms", request->duration_ms);
    return finish_message(root, buffer, buffer_len);
}

esp_err_t usaki_protocol_build_voice_input_cancel(const usaki_protocol_voice_input_cancel_t *request,
                                                  char *buffer,
                                                  size_t buffer_len)
{
    cJSON *data = NULL;
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");

    cJSON *root = create_message_root(&request->header, "voice.input.cancel", &data);
    if (root == NULL)
    {
        return ESP_ERR_NO_MEM;
    }
    cJSON_AddStringToObject(data, "request_id", safe_string(request->request_id));
    cJSON_AddStringToObject(data, "reason", string_or_default(request->reason, "user_cancel"));
    return finish_message(root, buffer, buffer_len);
}

esp_err_t usaki_protocol_build_voice_wake_detected(const usaki_protocol_voice_wake_detected_t *request,
                                                   char *buffer,
                                                   size_t buffer_len)
{
    cJSON *data = NULL;
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");

    cJSON *root = create_message_root(&request->header, "voice.wake.detected", &data);
    if (root == NULL)
    {
        return ESP_ERR_NO_MEM;
    }
    cJSON_AddStringToObject(data, "wake_word", safe_string(request->wake_word));
    cJSON_AddNumberToObject(data, "confidence", request->confidence);
    cJSON_AddStringToObject(data, "input_mode", string_or_default(request->input_mode, "wake_word"));
    cJSON_AddBoolToObject(data, "will_start_input", request->will_start_input);
    return finish_message(root, buffer, buffer_len);
}

esp_err_t usaki_protocol_build_voice_interrupt(const usaki_protocol_voice_interrupt_t *request,
                                               char *buffer,
                                               size_t buffer_len)
{
    cJSON *data = NULL;
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");

    cJSON *root = create_message_root(&request->header, "voice.interrupt", &data);
    if (root == NULL)
    {
        return ESP_ERR_NO_MEM;
    }
    cJSON_AddStringToObject(data, "output_id", safe_string(request->output_id));
    cJSON_AddStringToObject(data, "reason", string_or_default(request->reason, "user_speaking"));
    return finish_message(root, buffer, buffer_len);
}

esp_err_t usaki_protocol_build_touch_event(const usaki_protocol_touch_event_t *request,
                                           char *buffer,
                                           size_t buffer_len)
{
    cJSON *data = NULL;
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");

    cJSON *root = create_message_root(&request->header, "touch.event", &data);
    if (root == NULL)
    {
        return ESP_ERR_NO_MEM;
    }
    cJSON_AddStringToObject(data, "area", safe_string(request->area));
    cJSON_AddStringToObject(data, "event", safe_string(request->event));
    cJSON_AddNumberToObject(data, "value", request->value);
    cJSON_AddNumberToObject(data, "duration_ms", request->duration_ms);
    return finish_message(root, buffer, buffer_len);
}

esp_err_t usaki_protocol_build_sensor_update(const usaki_protocol_sensor_update_t *request,
                                             char *buffer,
                                             size_t buffer_len)
{
    cJSON *data = NULL;
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");

    cJSON *root = create_message_root(&request->header, "sensor.update", &data);
    if (root == NULL)
    {
        return ESP_ERR_NO_MEM;
    }

    cJSON *imu = cJSON_CreateObject();
    if (imu == NULL)
    {
        cJSON_Delete(root);
        return ESP_ERR_NO_MEM;
    }
    cJSON_AddNumberToObject(imu, "x", request->imu.x);
    cJSON_AddNumberToObject(imu, "y", request->imu.y);
    cJSON_AddNumberToObject(imu, "z", request->imu.z);
    cJSON_AddItemToObject(data, "imu", imu);
    cJSON_AddNumberToObject(data, "light", request->light);
    cJSON_AddNumberToObject(data, "distance", request->distance);
    return finish_message(root, buffer, buffer_len);
}

esp_err_t usaki_protocol_build_error(const usaki_protocol_error_t *request,
                                     char *buffer,
                                     size_t buffer_len)
{
    cJSON *data = NULL;
    ESP_RETURN_ON_FALSE(request != NULL, ESP_ERR_INVALID_ARG, TAG, "request is null");

    cJSON *root = create_message_root(&request->header, "error", &data);
    if (root == NULL)
    {
        return ESP_ERR_NO_MEM;
    }
    cJSON_AddStringToObject(data, "ref_id", safe_string(request->ref_id));
    cJSON_AddNumberToObject(data, "code", request->code);
    cJSON_AddStringToObject(data, "message", safe_string(request->message));
    cJSON_AddBoolToObject(data, "retryable", request->retryable);
    return finish_message(root, buffer, buffer_len);
}

static usaki_protocol_server_message_type_t classify_type(const char *type)
{
    if (type == NULL)
    {
        return USAKI_PROTOCOL_SERVER_MESSAGE_UNKNOWN;
    }
    if (strcmp(type, "voice.output.start") == 0)
    {
        return USAKI_PROTOCOL_SERVER_MESSAGE_VOICE_OUTPUT_START;
    }
    if (strcmp(type, "voice.output.end") == 0)
    {
        return USAKI_PROTOCOL_SERVER_MESSAGE_VOICE_OUTPUT_END;
    }
    if (strcmp(type, "voice.output.cancel") == 0)
    {
        return USAKI_PROTOCOL_SERVER_MESSAGE_VOICE_OUTPUT_CANCEL;
    }
    if (strcmp(type, "emotion.update") == 0)
    {
        return USAKI_PROTOCOL_SERVER_MESSAGE_EMOTION_UPDATE;
    }
    if (strcmp(type, "eye.animation") == 0)
    {
        return USAKI_PROTOCOL_SERVER_MESSAGE_EYE_ANIMATION;
    }
    if (strcmp(type, "body.action") == 0)
    {
        return USAKI_PROTOCOL_SERVER_MESSAGE_BODY_ACTION;
    }
    if (strcmp(type, "motion.servo.batch") == 0)
    {
        return USAKI_PROTOCOL_SERVER_MESSAGE_MOTION_SERVO_BATCH;
    }
    if (strcmp(type, "notification.push") == 0)
    {
        return USAKI_PROTOCOL_SERVER_MESSAGE_NOTIFICATION_PUSH;
    }
    if (strcmp(type, "error") == 0)
    {
        return USAKI_PROTOCOL_SERVER_MESSAGE_ERROR;
    }
    return USAKI_PROTOCOL_SERVER_MESSAGE_UNKNOWN;
}

esp_err_t usaki_protocol_parse_server_message(const char *json,
                                              size_t json_len,
                                              usaki_protocol_server_message_t *out)
{
    ESP_RETURN_ON_FALSE(json != NULL, ESP_ERR_INVALID_ARG, TAG, "json is null");
    ESP_RETURN_ON_FALSE(out != NULL, ESP_ERR_INVALID_ARG, TAG, "out is null");

    cJSON *root = cJSON_ParseWithLength(json, json_len);
    ESP_RETURN_ON_FALSE(root != NULL, ESP_ERR_INVALID_RESPONSE, TAG, "invalid json");

    memset(out, 0, sizeof(*out));
    copy_json_string(root, "id", out->id, sizeof(out->id));
    copy_json_string(root, "type", out->type_name, sizeof(out->type_name));
    copy_json_string(root, "device_id", out->device_id, sizeof(out->device_id));
    out->type = classify_type(out->type_name);
    out->timestamp = (int64_t)json_double(root, "timestamp", 0);
    out->seq = json_int(root, "seq", 0);

    cJSON *data = cJSON_GetObjectItemCaseSensitive(root, "data");
    if (!cJSON_IsObject(data))
    {
        cJSON_Delete(root);
        return ESP_OK;
    }

    out->success = json_bool(data, "success", false);
    out->code = json_int(data, "code", 0);
    out->retryable = json_bool(data, "retryable", false);
    out->duration_ms = json_int(data, "duration_ms", 0);
    out->frame_duration_ms = json_int(data, "frame_duration_ms", 0);
    out->sample_rate = json_int(data, "sample_rate", 0);
    out->channels = json_int(data, "channels", 0);
    out->sample_bits = json_int(data, "sample_bits", 0);
    out->intensity = (float)json_double(data, "intensity", 0);
    out->loop = json_bool(data, "loop", false);
    out->interrupt = json_bool(data, "interrupt", false);
    out->priority = json_int(data, "priority", 0);
    out->ttl_ms = json_int(data, "ttl_ms", 0);

    copy_json_string(data, "ref_id", out->ref_id, sizeof(out->ref_id));
    copy_json_string(data, "message", out->message, sizeof(out->message));
    copy_json_string(data, "request_id", out->request_id, sizeof(out->request_id));
    copy_json_string(data, "output_id", out->output_id, sizeof(out->output_id));
    copy_json_string(data, "command_id", out->command_id, sizeof(out->command_id));
    copy_json_string(data, "source", out->source, sizeof(out->source));
    copy_json_string(data, "name", out->name, sizeof(out->name));
    copy_json_string(data, "emotion", out->emotion, sizeof(out->emotion));
    copy_json_string(data, "reason", out->reason, sizeof(out->reason));
    copy_json_string(data, "codec", out->codec, sizeof(out->codec));
    if (out->type == USAKI_PROTOCOL_SERVER_MESSAGE_BODY_ACTION)
    {
        parse_body_actions(data, out);
    }
    if (out->type == USAKI_PROTOCOL_SERVER_MESSAGE_MOTION_SERVO_BATCH)
    {
        parse_motion_servo_batch(data, out);
    }

    cJSON_Delete(root);
    return ESP_OK;
}
