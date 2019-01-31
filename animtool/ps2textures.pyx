# cython: cdivision=True
# cython: boundscheck=False
# cython: wraparound=False
# cython: language_level=3

# Source: Victor Suba's swizzle code
# http://ps2linux.no-ip.info/playstation2-linux.com/projects/ezswizzle/index.html
# This Python port is not guaranteed to be working and will not be maintained beyond what I need for my personal project.

from cpython cimport array
from libc.stdlib cimport malloc, free

import os

cdef int *palette_idx = [0, 1, 2, 3, 4, 5, 6, 7, 16, 17, 18, 19, 20, 21, 22, 23, 8, 9, 10, 11, 12, 13, 14, 15, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 48, 49, 50, 51, 52, 53, 54, 55, 40, 41, 42, 43, 44, 45, 46, 47, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 80, 81, 82, 83, 84, 85, 86, 87, 72, 73, 74, 75, 76, 77, 78, 79, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 112, 113, 114, 115, 116, 117, 118, 119, 104, 105, 106, 107, 108, 109, 110, 111, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 144, 145, 146, 147, 148, 149, 150, 151, 136, 137, 138, 139, 140, 141, 142, 143, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 176, 177, 178, 179, 180, 181, 182, 183, 168, 169, 170, 171, 172, 173, 174, 175, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 208, 209, 210, 211, 212, 213, 214, 215, 200, 201, 202, 203, 204, 205, 206, 207, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 240, 241, 242, 243, 244, 245, 246, 247, 232, 233, 234, 235, 236, 237, 238, 239, 248, 249, 250, 251, 252, 253, 254, 255]

def decode_ps2_texture(str filename, int width, int height, int bpp):
    if not os.path.exists(filename):
        print("Couldn't find image", filename)
        return None

    _data_raw = bytearray(open(filename, "rb").read())

    cdef array.array data_raw = array.array('B', _data_raw)
    cdef unsigned char *gsmem = <unsigned char*>malloc(1024 * 1024 * 4)

    cdef int palette_len = 0x400
    cdef unsigned char *data = data_raw.data.as_uchars
    cdef unsigned int *palette_data = <unsigned int*>data
    cdef unsigned char *image_data = data + palette_len
    cdef unsigned int *image_data_int = <unsigned int*>image_data
    cdef unsigned int *gsmem_int = <unsigned int*>gsmem
    cdef int image_data_len = width * height

    cdef unsigned int MASK_ALPHA = 0xff000000
    cdef unsigned int MASK_R = 0x00ff0000
    cdef unsigned int MASK_G = 0x0000ff00
    cdef unsigned int MASK_B = 0x000000ff
    cdef unsigned int MASK_RGB = MASK_R | MASK_G | MASK_B
    cdef unsigned int color
    cdef unsigned int a

    cdef int i, j

    cdef int rrw = width / 2
    cdef int rrh = height / 2

    raw_image_data = bytearray(width * height)

    writeTexPSMCT32(0, rrw / 0x40, 0, 0, rrw, rrh, image_data_int, gsmem_int)
    readTexPSMT8(0, width / 0x40, 0, 0, width, height, raw_image_data, gsmem)

    i = 0
    while i < palette_len / 4:
        color = palette_data[i]
        a = color & MASK_ALPHA
        a >>= 24
        a = int(0xff * (a / 128))

        palette_data[i] = (color & MASK_RGB) | (a << 24)
        i += 1

    # Output RGBA data
    decoded_raw_image = bytearray(image_data_len * 4)

    i = 0
    j = 0
    while i < image_data_len:
        decoded_raw_image[j] = (palette_data[palette_idx[raw_image_data[i]]] & 0x000000ff)
        decoded_raw_image[j + 1] = (palette_data[palette_idx[raw_image_data[i]]] & 0x0000ff00) >> 8
        decoded_raw_image[j + 2] = (palette_data[palette_idx[raw_image_data[i]]] & 0x00ff0000) >> 16
        decoded_raw_image[j + 3] = (palette_data[palette_idx[raw_image_data[i]]] & 0xff000000) >> 24
        i += 1
        j += 4

    output = [decoded_raw_image[x] for x in range(0, image_data_len * 4)]
    free(gsmem)

    return output


cdef int *block32 = [
     0,  1,  4,  5, 16, 17, 20, 21,
     2,  3,  6,  7, 18, 19, 22, 23,
     8,  9, 12, 13, 24, 25, 28, 29,
    10, 11, 14, 15, 26, 27, 30, 31
]

cdef int *columnWord32 = [
     0,  1,  4,  5,  8,  9, 12, 13,
     2,  3,  6,  7, 10, 11, 14, 15
]

cdef writeTexPSMCT32(int dbp, int dbw, int dsax, int dsay, int rrw, int rrh, unsigned int *data, unsigned int *gsmem):
    cdef int startBlockPos = dbp * 64
    cdef int page, pageX, pageY, px, py, blockX, blockY, block, bx, by, column, cx, cy, cw
    cdef int data_idx = 0
    cdef int x = 0
    cdef int y = 0

    y = dsay
    while y < dsay + rrh:
        x = dsax

        while x < dsax + rrw:
            pageX = x / 64
            pageY = y / 32
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
            x += 1

        y += 1


cdef int *block8 = [
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

cdef int *columnByte8 = [
    0, 0, 0, 0, 0, 0, 0, 0,  2, 2, 2, 2, 2, 2, 2, 2,
    0, 0, 0, 0, 0, 0, 0, 0,  2, 2, 2, 2, 2, 2, 2, 2,

    1, 1, 1, 1, 1, 1, 1, 1,  3, 3, 3, 3, 3, 3, 3, 3,
    1, 1, 1, 1, 1, 1, 1, 1,  3, 3, 3, 3, 3, 3, 3, 3
]


cdef readTexPSMT8(int dbp, int dbw, int dsax, int dsay, int rrw, int rrh, unsigned char *data, unsigned char *gsmem):
    cdef int startBlockPos = dbp * 64
    cdef int page, pageX, pageY, px, py, blockX, blockY, block, bx, by, column, cx, cy, cw, cb
    cdef int data_idx = 0
    cdef int x = 0
    cdef int y = 0

    dbw >>= 1

    y = dsay
    while y < dsay + rrh:
        x = dsax

        while x < dsax + rrw:
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
            x += 1

        y += 1
