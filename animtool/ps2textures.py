# Source: Victor Suba's swizzle code
# http://ps2linux.no-ip.info/playstation2-linux.com/projects/ezswizzle/index.html
# This Python port is not guaranteed to be working and will not be maintained beyond what I need for my personal project.

import os
import struct
import sys

from io import BytesIO

palette_idx = [0, 1, 2, 3, 4, 5, 6, 7, 16, 17, 18, 19, 20, 21, 22, 23, 8, 9, 10, 11, 12, 13, 14, 15, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 48, 49, 50, 51, 52, 53, 54, 55, 40, 41, 42, 43, 44, 45, 46, 47, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 80, 81, 82, 83, 84, 85, 86, 87, 72, 73, 74, 75, 76, 77, 78, 79, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 112, 113, 114, 115, 116, 117, 118, 119, 104, 105, 106, 107, 108, 109, 110, 111, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 144, 145, 146, 147, 148, 149, 150, 151, 136, 137, 138, 139, 140, 141, 142, 143, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 176, 177, 178, 179, 180, 181, 182, 183, 168, 169, 170, 171, 172, 173, 174, 175, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 208, 209, 210, 211, 212, 213, 214, 215, 200, 201, 202, 203, 204, 205, 206, 207, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 240, 241, 242, 243, 244, 245, 246, 247, 232, 233, 234, 235, 236, 237, 238, 239, 248, 249, 250, 251, 252, 253, 254, 255]


#@profile
def decode_ps2_texture(filename, width, height, bpp):
    if not os.path.exists(filename):
        print("Couldn't find image", filename)
        return None

    data = bytearray(open(filename, "rb").read())

    palette_len = 0x400
    palette_data = list(struct.unpack("<" + "I" * (palette_len // 4), data[:palette_len]))
    image_data = data[palette_len:]
    image_data_len = len(image_data)

    if bpp == 8:
        rrw = width // 2
        rrh = height // 2

        gsmem = writeTexPSMCT32(0, rrw // 0x40, 0, 0, rrw, rrh, image_data)
        image_data = readTexPSMT8(0, width // 0x40, 0, 0, width, height, image_data, gsmem)

    else:
        rrw = width // 2
        rrh = height // 4

        gsmem = writeTexPSMCT32(0, rrw // 0x40, 0, 0, rrw, rrh, image_data)
        image_data = readTexPSMT4(0, width // 0x40, 0, 0, width, height, image_data, gsmem)

    # Output RGBA data
    decoded_raw_image = []

    for idx, color in enumerate(palette_data):
        a = (color & 0xff000000) >> 24
        a = int(0xff * (a / 128))

        palette_data[idx] = (color & 0x00ffffff) | (a << 24)

    for i in range(0, image_data_len):
        decoded_raw_image += struct.pack("<I", palette_data[palette_idx[image_data[i]]])

    return bytes(decoded_raw_image)


#@profile
def reshape_buffer(gsmem, input_size, output_size):
    fmt = {
        1: "B",
        2: "H",
        4: "I",
    }

    if isinstance(gsmem, list):
        return struct.pack("<" + str((len(gsmem) * 4) // (max(input_size, output_size) // min(input_size, output_size))) + fmt[input_size], *gsmem)

    return struct.unpack("<" + str(len(gsmem) // (max(input_size, output_size) // min(input_size, output_size))) + fmt[output_size], gsmem)





block32 = [
     0,  1,  4,  5, 16, 17, 20, 21,
     2,  3,  6,  7, 18, 19, 22, 23,
     8,  9, 12, 13, 24, 25, 28, 29,
    10, 11, 14, 15, 26, 27, 30, 31
]

columnWord32 = [
     0,  1,  4,  5,  8,  9, 12, 13,
     2,  3,  6,  7, 10, 11, 14, 15
]

#@profile
def writeTexPSMCT32(dbp, dbw, dsax, dsay, rrw, rrh, data):
    gsmem = [0] * (1024 * 1024)

    data = reshape_buffer(data, 1, 4)
    data_idx = 0

    startBlockPos = dbp * 64

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 64
            pageY = y // 32
            page  = pageX + pageY * dbw

            px = x - (pageX * 64)
            py = y - (pageY * 32)

            blockX = px // 8
            blockY = py // 8
            block  = block32[blockX + blockY * 8]

            bx = px - blockX * 8
            by = py - blockY * 8

            column = by // 2

            cx = bx
            cy = by - column * 2
            cw = columnWord32[cx + cy * 8]

            gsmem[startBlockPos + page * 2048 + block * 64 + column * 16 + cw] = data[data_idx]
            data_idx += 1

    return reshape_buffer(gsmem, 4, 1)


#@profile
def readTexPSMCT32(dbp, dbw, dsax, dsay, rrw, rrh, data, gsmem):
    gsmem = reshape_buffer(gsmem, 1, 4)

    data = reshape_buffer(data, 1, 4)
    data_idx = 0

    startBlockPos = dbp * 64

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 64
            pageY = y // 32
            page  = pageX + pageY * dbw

            px = x - (pageX * 64)
            py = y - (pageY * 32)

            blockX = px // 8
            blockY = py // 8
            block  = block32[blockX + blockY * 8]

            bx = px - blockX * 8
            by = py - blockY * 8

            column = by // 2

            cx = bx
            cy = by - column * 2
            cw = columnWord32[cx + cy * 8]

            data[data_idx] = gsmem[startBlockPos + page * 2048 + block * 64 + column * 16 + cw]
            data_idx += 1

    return reshape_buffer(data, 4, 1)


blockZ32 = [
     24, 25, 28, 29, 8, 9, 12, 13,
     26, 27, 30, 31,10, 11, 14, 15,
     16, 17, 20, 21, 0, 1, 4, 5,
     18, 19, 22, 23, 2, 3, 6, 7
]

columnWordZ32 = [
     0,  1,  4,  5,  8,  9, 12, 13,
     2,  3,  6,  7, 10, 11, 14, 15
]

#@profile
def writeTexPSMZ32(dbp, dbw, dsax, dsay, rrw, rrh, data):
    gsmem = [0] * (1024 * 1024)

    data = reshape_buffer(data, 1, 4)
    data_idx = 0

    startBlockPos = dbp * 64

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 64
            pageY = y // 32
            page  = pageX + pageY * dbw

            px = x - (pageX * 64)
            py = y - (pageY * 32)

            blockX = px // 8
            blockY = py // 8
            block  = blockZ32[blockX + blockY * 8]

            bx = px - blockX * 8
            by = py - blockY * 8

            column = by // 2

            cx = bx
            cy = by - column * 2
            cw = columnWordZ32[cx + cy * 8]

            gsmem[startBlockPos + page * 2048 + block * 64 + column * 16 + cw] = data[data_idx]
            data_idx += 1

    return reshape_buffer(gsmem, 4, 1)


#@profile
def readTexPSMZ32(dbp, dbw, dsax, dsay, rrw, rrh, data, gsmem):
    gsmem = reshape_buffer(gsmem, 1, 4)

    data = reshape_buffer(data, 1, 4)
    data_idx = 0

    startBlockPos = dbp * 64

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 64
            pageY = y // 32
            page  = pageX + pageY * dbw

            px = x - (pageX * 64)
            py = y - (pageY * 32)

            blockX = px // 8
            blockY = py // 8
            block  = blockZ32[blockX + blockY * 8]

            bx = px - blockX * 8
            by = py - blockY * 8

            column = by // 2

            cx = bx
            cy = by - column * 2
            cw = columnWordZ32[cx + cy * 8]

            data[data_idx] = gsmem[startBlockPos + page * 2048 + block * 64 + column * 16 + cw]
            data_idx += 1

    return reshape_buffer(data, 4, 1)


block16 = [
     0,  2,  8, 10,
     1,  3,  9, 11,
     4,  6, 12, 14,
     5,  7, 13, 15,
    16, 18, 24, 26,
    17, 19, 25, 27,
    20, 22, 28, 30,
    21, 23, 29, 31
]

columnWord16 = [
     0,  1,  4,  5,  8,  9, 12, 13,   0,  1,  4,  5,  8,  9, 12, 13,
     2,  3,  6,  7, 10, 11, 14, 15,   2,  3,  6,  7, 10, 11, 14, 15
]

columnHalf16 = [
    0, 0, 0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1,
    0, 0, 0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1
]

#@profile
def writeTexPSMCT16(dbp, dbw, dsax, dsay, rrw, rrh, data):
    gsmem = [0] * (1024 * 1024 * 2)

    data = reshape_buffer(data, 1, 2)
    data_idx = 0

    startBlockPos = dbp * 64

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 64
            pageY = y // 64
            page  = pageX + pageY * dbw

            px = x - (pageX * 64)
            py = y - (pageY * 64)

            blockX = px // 16
            blockY = py // 8
            block  = block16[blockX + blockY * 4]

            bx = px - blockX * 16
            by = py - blockY * 8

            column = by // 2

            cx = bx
            cy = by - column * 2
            cw = columnWord16[cx + cy * 16]
            ch = columnHalf16[cx + cy * 16]

            gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 2 + ch] = data[data_idx]
            data_idx += 1

    return reshape_buffer(gsmem, 2, 1)


#@profile
def readTexPSMCT16(dbp, dbw, dsax, dsay, rrw, rrh, data, gsmem):
    gsmem = reshape_buffer(gsmem, 1, 2)

    data = reshape_buffer(data, 1, 2)
    data_idx = 0

    startBlockPos = dbp * 64

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 64
            pageY = y // 64
            page  = pageX + pageY * dbw

            px = x - (pageX * 64)
            py = y - (pageY * 64)

            blockX = px // 16
            blockY = py // 8
            block  = block16[blockX + blockY * 4]

            bx = px - blockX * 16
            by = py - blockY * 8

            column = by // 2

            cx = bx
            cy = by - column * 2
            cw = columnWord16[cx + cy * 16]
            ch = columnHalf16[cx + cy * 16]

            data[data_idx] = gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 2 + ch]
            data_idx += 1

    return reshape_buffer(data, 2, 1)


blockZ16 = [
     24,  26,  16, 18,
     25,  27,  17, 19,
    28,  30, 20, 22,
     29,  31, 21, 23,
    8, 10, 0, 2,
    9, 11, 1, 3,
    12, 14, 4, 6,
    13, 15, 5, 7
]

columnWordZ16 = [
     0,  1,  4,  5,  8,  9, 12, 13,   0,  1,  4,  5,  8,  9, 12, 13,
     2,  3,  6,  7, 10, 11, 14, 15,   2,  3,  6,  7, 10, 11, 14, 15
]

columnHalfZ16 = [
    0, 0, 0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1,
    0, 0, 0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1
]

#@profile
def writeTexPSMZ16(dbp, dbw, dsax, dsay, rrw, rrh, data):
    gsmem = [0] * (1024 * 1024 * 2)

    data = reshape_buffer(data, 1, 2)
    data_idx = 0

    startBlockPos = dbp * 64

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 64
            pageY = y // 64
            page  = pageX + pageY * dbw

            px = x - (pageX * 64)
            py = y - (pageY * 64)

            blockX = px // 16
            blockY = py // 8
            block  = blockZ16[blockX + blockY * 4]

            bx = px - blockX * 16
            by = py - blockY * 8

            column = by // 2

            cx = bx
            cy = by - column * 2
            cw = columnWordZ16[cx + cy * 16]
            ch = columnHalfZ16[cx + cy * 16]

            gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 2 + ch] = data[data_idx]
            data_idx += 1

    return reshape_buffer(gsmem, 2, 1)


#@profile
def readTexPSMZ16(dbp, dbw, dsax, dsay, rrw, rrh, data, gsmem):
    gsmem = reshape_buffer(gsmem, 1, 2)

    data = reshape_buffer(data, 1, 2)
    data_idx = 0

    startBlockPos = dbp * 64

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 64
            pageY = y // 64
            page  = pageX + pageY * dbw

            px = x - (pageX * 64)
            py = y - (pageY * 64)

            blockX = px // 16
            blockY = py // 8
            block  = blockZ16[blockX + blockY * 4]

            bx = px - blockX * 16
            by = py - blockY * 8

            column = by // 2

            cx = bx
            cy = by - column * 2
            cw = columnWordZ16[cx + cy * 16]
            ch = columnHalfZ16[cx + cy * 16]

            data[data_idx] = gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 2 + ch]
            data_idx += 1

    return reshape_buffer(data, 2, 1)


blockZ16S = [
     24,  26,  8, 10,
     25,  27,  9, 11,
     16,  18, 0, 2,
     17,  19, 1, 3,
    28, 30, 12, 14,
    29, 31, 13, 15,
    20, 22, 4, 6,
    21, 23, 5, 7
]

columnWordZ16S = [
     0,  1,  4,  5,  8,  9, 12, 13,   0,  1,  4,  5,  8,  9, 12, 13,
     2,  3,  6,  7, 10, 11, 14, 15,   2,  3,  6,  7, 10, 11, 14, 15
]

columnHalfZ16S = [
    0, 0, 0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1,
    0, 0, 0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1
]

#@profile
def writeTexPSMZ16S(dbp, dbw, dsax, dsay, rrw, rrh, data):
    gsmem = [0] * (1024 * 1024 * 2)

    data = reshape_buffer(data, 1, 2)
    data_idx = 0

    startBlockPos = dbp * 64

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 64
            pageY = y // 64
            page  = pageX + pageY * dbw

            px = x - (pageX * 64)
            py = y - (pageY * 64)

            blockX = px // 16
            blockY = py // 8
            block  = blockZ16S[blockX + blockY * 4]

            bx = px - blockX * 16
            by = py - blockY * 8

            column = by // 2

            cx = bx
            cy = by - column * 2
            cw = columnWordZ16S[cx + cy * 16]
            ch = columnHalfZ16S[cx + cy * 16]

            gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 2 + ch] = data[data_idx]
            data_idx += 1

    return reshape_buffer(gsmem, 2, 1)


#@profile
def readTexPSMZ16S(dbp, dbw, dsax, dsay, rrw, rrh, data, gsmem):
    gsmem = reshape_buffer(gsmem, 1, 2)

    data = reshape_buffer(data, 1, 2)
    data_idx = 0

    startBlockPos = dbp * 64

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 64
            pageY = y // 64
            page  = pageX + pageY * dbw

            px = x - (pageX * 64)
            py = y - (pageY * 64)

            blockX = px // 16
            blockY = py // 8
            block  = blockZ16S[blockX + blockY * 4]

            bx = px - blockX * 16
            by = py - blockY * 8

            column = by // 2

            cx = bx
            cy = by - column * 2
            cw = columnWordZ16S[cx + cy * 16]
            ch = columnHalfZ16S[cx + cy * 16]

            data[data_idx] = gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 2 + ch]
            data_idx += 1

    return reshape_buffer(data, 2, 1)


block16S = [
     0,  2, 16, 18,
     1,  3, 17, 19,
     8, 10, 24, 26,
     9, 11, 25, 27,
     4,  6, 20, 22,
     5,  7, 21, 23,
    12, 14, 28, 30,
    13, 15, 29, 31
]

columnWord16S = [
     0,  1,  4,  5,  8,  9, 12, 13,   0,  1,  4,  5,  8,  9, 12, 13,
     2,  3,  6,  7, 10, 11, 14, 15,   2,  3,  6,  7, 10, 11, 14, 15
]

columnHalf16S = [
    0, 0, 0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1,
    0, 0, 0, 0, 0, 0, 0, 0,  1, 1, 1, 1, 1, 1, 1, 1
]

#@profile
def writeTexPSMCT16S(dbp, dbw, dsax, dsay, rrw, rrh, data):
    gsmem = [0] * (1024 * 1024 * 2)

    data = reshape_buffer(data, 1, 2)
    data_idx = 0

    startBlockPos = dbp * 64

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 64
            pageY = y // 64
            page  = pageX + pageY * dbw

            px = x - (pageX * 64)
            py = y - (pageY * 64)

            blockX = px // 16
            blockY = py // 8
            block  = block16S[blockX + blockY * 4]

            bx = px - blockX * 16
            by = py - blockY * 8

            column = by // 2

            cx = bx
            cy = by - column * 2
            cw = columnWord16S[cx + cy * 16]
            ch = columnHalf16S[cx + cy * 16]

            gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 2 + ch] = data[data_idx]
            data_idx += 1

    return reshape_buffer(gsmem, 2, 1)


#@profile
def readTexPSMCT16S(dbp, dbw, dsax, dsay, rrw, rrh, data, gsmem):
    gsmem = reshape_buffer(gsmem, 1, 2)

    data = reshape_buffer(data, 1, 2)
    data_idx = 0

    startBlockPos = dbp * 64

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 64
            pageY = y // 64
            page  = pageX + pageY * dbw

            px = x - (pageX * 64)
            py = y - (pageY * 64)

            blockX = px // 16
            blockY = py // 8
            block  = block16S[blockX + blockY * 4]

            bx = px - blockX * 16
            by = py - blockY * 8

            column = by // 2

            cx = bx
            cy = by - column * 2
            cw = columnWord16S[cx + cy * 16]
            ch = columnHalf16S[cx + cy * 16]

            data[data_idx] = gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 2 + ch]
            data_idx += 1

    return reshape_buffer(data, 2, 1)


block8 = [
     0,  1,  4,  5, 16, 17, 20, 21,
     2,  3,  6,  7, 18, 19, 22, 23,
     8,  9, 12, 13, 24, 25, 28, 29,
    10, 11, 14, 15, 26, 27, 30, 31
]

columnWord8 = [
    [
         0,  1,  4,  5,  8,  9, 12, 13,   0,  1,  4,  5,  8,  9, 12, 13,
         2,  3,  6,  7, 10, 11, 14, 15,   2,  3,  6,  7, 10, 11, 14, 15,

         8,  9, 12, 13,  0,  1,  4,  5,   8,  9, 12, 13,  0,  1,  4,  5,
        10, 11, 14, 15,  2,  3,  6,  7,  10, 11, 14, 15,  2,  3,  6,  7
    ],
    [
         8,  9, 12, 13,  0,  1,  4,  5,   8,  9, 12, 13,  0,  1,  4,  5,
        10, 11, 14, 15,  2,  3,  6,  7,  10, 11, 14, 15,  2,  3,  6,  7,

         0,  1,  4,  5,  8,  9, 12, 13,   0,  1,  4,  5,  8,  9, 12, 13,
         2,  3,  6,  7, 10, 11, 14, 15,   2,  3,  6,  7, 10, 11, 14, 15
    ]
]

columnByte8 = [
    0, 0, 0, 0, 0, 0, 0, 0,  2, 2, 2, 2, 2, 2, 2, 2,
    0, 0, 0, 0, 0, 0, 0, 0,  2, 2, 2, 2, 2, 2, 2, 2,

    1, 1, 1, 1, 1, 1, 1, 1,  3, 3, 3, 3, 3, 3, 3, 3,
    1, 1, 1, 1, 1, 1, 1, 1,  3, 3, 3, 3, 3, 3, 3, 3
]

#@profile
def writeTexPSMT8(dbp, dbw, dsax, dsay, rrw, rrh, data):
    gsmem = [0] * (1024 * 1024 * 4)

    data_idx = 0
    startBlockPos = dbp * 64

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 128
            pageY = y // 64
            page  = pageX + pageY * dbw

            px = x - (pageX * 128)
            py = y - (pageY * 64)

            blockX = px // 16
            blockY = py // 16
            block  = block8[blockX + blockY * 8]

            bx = px - (blockX * 16)
            by = py - (blockY * 16)

            column = by // 4

            cx = bx
            cy = by - column * 4
            cw = columnWord8[column & 1][cx + cy * 16]
            cb = columnByte8[cx + cy * 16]

            gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + cb] = data[data_idx]
            data_idx += 1

    return gsmem


#@profile
def readTexPSMT8(dbp, dbw, dsax, dsay, rrw, rrh, data, gsmem):
    data_idx = 0
    startBlockPos = dbp * 64

    dbw >>= 1

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 128
            pageY = y // 64
            page  = pageX + pageY * dbw

            px = x - (pageX * 128)
            py = y - (pageY * 64)

            blockX = px // 16
            blockY = py // 16
            block  = block8[blockX + blockY * 8]

            bx = px - blockX * 16
            by = py - blockY * 16

            column = by // 4

            cx = bx
            cy = by - column * 4
            cw = columnWord8[column & 1][cx + cy * 16]
            cb = columnByte8[cx + cy * 16]

            data[data_idx] = gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + cb]
            data_idx += 1

    return data


block4 = [
     0,  2,  8, 10,
     1,  3,  9, 11,
     4,  6, 12, 14,
     5,  7, 13, 15,
    16, 18, 24, 26,
    17, 19, 25, 27,
    20, 22, 28, 30,
    21, 23, 29, 31
]

columnWord4 = [
    [
         0,  1,  4,  5,  8,  9, 12, 13,   0,  1,  4,  5,  8,  9, 12, 13,   0,  1,  4,  5,  8,  9, 12, 13,   0,  1,  4,  5,  8,  9, 12, 13,
         2,  3,  6,  7, 10, 11, 14, 15,   2,  3,  6,  7, 10, 11, 14, 15,   2,  3,  6,  7, 10, 11, 14, 15,   2,  3,  6,  7, 10, 11, 14, 15,

         8,  9, 12, 13,  0,  1,  4,  5,   8,  9, 12, 13,  0,  1,  4,  5,   8,  9, 12, 13,  0,  1,  4,  5,   8,  9, 12, 13,  0,  1,  4,  5,
        10, 11, 14, 15,  2,  3,  6,  7,  10, 11, 14, 15,  2,  3,  6,  7,  10, 11, 14, 15,  2,  3,  6,  7,  10, 11, 14, 15,  2,  3,  6,  7
    ],
    [
         8,  9, 12, 13,  0,  1,  4,  5,   8,  9, 12, 13,  0,  1,  4,  5,   8,  9, 12, 13,  0,  1,  4,  5,   8,  9, 12, 13,  0,  1,  4,  5,
        10, 11, 14, 15,  2,  3,  6,  7,  10, 11, 14, 15,  2,  3,  6,  7,  10, 11, 14, 15,  2,  3,  6,  7,  10, 11, 14, 15,  2,  3,  6,  7,

         0,  1,  4,  5,  8,  9, 12, 13,   0,  1,  4,  5,  8,  9, 12, 13,   0,  1,  4,  5,  8,  9, 12, 13,   0,  1,  4,  5,  8,  9, 12, 13,
         2,  3,  6,  7, 10, 11, 14, 15,   2,  3,  6,  7, 10, 11, 14, 15,   2,  3,  6,  7, 10, 11, 14, 15,   2,  3,  6,  7, 10, 11, 14, 15
    ]
]

columnByte4 = [
    0, 0, 0, 0, 0, 0, 0, 0,  2, 2, 2, 2, 2, 2, 2, 2,  4, 4, 4, 4, 4, 4, 4, 4,  6, 6, 6, 6, 6, 6, 6, 6,
    0, 0, 0, 0, 0, 0, 0, 0,  2, 2, 2, 2, 2, 2, 2, 2,  4, 4, 4, 4, 4, 4, 4, 4,  6, 6, 6, 6, 6, 6, 6, 6,

    1, 1, 1, 1, 1, 1, 1, 1,  3, 3, 3, 3, 3, 3, 3, 3,  5, 5, 5, 5, 5, 5, 5, 5,  7, 7, 7, 7, 7, 7, 7, 7,
    1, 1, 1, 1, 1, 1, 1, 1,  3, 3, 3, 3, 3, 3, 3, 3,  5, 5, 5, 5, 5, 5, 5, 5,  7, 7, 7, 7, 7, 7, 7, 7
]

#@profile
def writeTexPSMT4(dbp, dbw, dsax, dsay, rrw, rrh, data):
    gsmem = [0] * (1024 * 1024 * 4)

    data_idx = 0
    startBlockPos = dbp * 64

    dbw >>= 1

    odd = False

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 128
            pageY = y // 128
            page  = pageX + pageY * dbw

            px = x - (pageX * 128)
            py = y - (pageY * 128)

            blockX = px // 32
            blockY = py // 16
            block  = block4[blockX + blockY * 4]

            bx = px - blockX * 32
            by = py - blockY * 16

            column = by // 4

            cx = bx
            cy = by - column * 4
            cw = columnWord4[column & 1][cx + cy * 32]
            cb = columnByte4[cx + cy * 32]

            if cb & 1:
                if odd:
                    gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + (cb >> 1)] = (gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + (cb >> 1)] & 0x0f) | ((data[data_idx]) & 0xf0)
                else:
                    gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + (cb >> 1)] = (gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + (cb >> 1)] & 0x0f) | (((data[data_idx]) << 4) & 0xf0)

            else:
                if odd:
                    gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + (cb >> 1)] = (gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + (cb >> 1)] & 0xf0) | (((data[data_idx]) >> 4) & 0x0f)
                else:
                    gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + (cb >> 1)] = (gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + (cb >> 1)] & 0xf0) | ((data[data_idx]) & 0x0f)

            if odd:
                data_idx += 1

            odd = not odd

    return gsmem


#@profile
def readTexPSMT4(dbp, dbw, dsax, dsay, rrw, rrh, data, gsmem):
    data_idx = 0
    startBlockPos = dbp * 64

    dbw >>= 1

    odd = False

    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 128
            pageY = y // 128
            page  = pageX + pageY * dbw

            px = x - (pageX * 128)
            py = y - (pageY * 128)

            blockX = px // 32
            blockY = py // 16
            block  = block4[blockX + blockY * 4]

            bx = px - blockX * 32
            by = py - blockY * 16

            column = by // 4

            cx = bx
            cy = by - column * 4
            cw = columnWord4[column & 1][cx + cy * 32]
            cb = columnByte4[cx + cy * 32]

            if cb & 1:
                if odd:
                    data[data_idx] = ((data[data_idx]) & 0x0f) | (gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + (cb >> 1)] & 0xf0)
                else:
                    data[data_idx] = ((data[data_idx]) & 0xf0) | ((gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + (cb >> 1)] >> 4) & 0x0f)

            else:
                if odd:
                    data[data_idx] = ((data[data_idx]) & 0x0f) | ((gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + (cb >> 1)] << 4) & 0xf0)
                else:
                    data[data_idx] = ((data[data_idx]) & 0xf0) | (gsmem[(startBlockPos + page * 2048 + block * 64 + column * 16 + cw) * 4 + (cb >> 1)] & 0x0f)

            if odd:
                data_idx += 1

            odd = not odd

    return data
