#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
// Pure bounded parser shared by embedded transport and host tests. Data includes
// the PN532 I2C ready byte followed by one normal response frame.
static inline bool spirit_pn532_parse_normal(const uint8_t *data, size_t size,
        uint8_t command, uint8_t *response, size_t *response_len) {
    if (!data || !response || !response_len || size < 10) return false;
    size_t len = data[4];
    if (!(data[0] & 1) || data[1] || data[2] || data[3] != 0xFF ||
        (uint8_t)(data[4] + data[5]) || len < 2 || len + 8 > size ||
        data[6] != 0xD5 || data[7] != (uint8_t)(command + 1)) return false;
    uint8_t sum = 0;
    for (size_t i = 6; i <= 6 + len; ++i) sum += data[i];
    if (sum || data[7 + len] != 0 || len - 2 > *response_len) return false;
    *response_len = len - 2;
    memcpy(response, data + 8, *response_len);
    return true;
}
