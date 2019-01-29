# cython: cdivision=True
# cython: boundscheck=False
# cython: wraparound=False
# cython: language_level=3

from cpython cimport array
from PIL import Image

def image_blend_1(src_img, dst_img, double opacity, double opacity2):
    cdef int i, j, cur_idx
    cdef double cur
    cdef int image_width = src_img.size[0]
    cdef int image_height = src_img.size[1]

    cdef unsigned char[:] src = array.array("B", src_img.tobytes())
    cdef unsigned char[:] dst = array.array("B", dst_img.tobytes())

    i = 0
    while i < image_width:
        j = 0

        while j < image_height:
            cur_idx = (i * 4) + (j * (image_width * 4))

            if src[cur_idx + 3] == 0:
                opacity2 = 1


            cur = src[cur_idx + 0] * opacity + dst[cur_idx + 0] * opacity2
            dst[cur_idx + 0] = 255 if cur > 255 else int(cur)

            cur = src[cur_idx + 1] * opacity + dst[cur_idx + 1] * opacity2
            dst[cur_idx + 1] = 255 if cur > 255 else int(cur)

            cur = src[cur_idx + 2] * opacity + dst[cur_idx + 2] * opacity2
            dst[cur_idx + 2] = 255 if cur > 255 else int(cur)

            cur = src[cur_idx + 3] * opacity + dst[cur_idx + 3] * opacity2
            dst[cur_idx + 3] = 255 if cur > 255 else int(cur)

            j += 1
        i += 1

    dst_new = Image.frombytes(dst_img.mode, dst_img.size, bytes(dst))
    dst_img.close()
    del dst_img

    return dst_new


def image_blend_2(src_img, dst_img, double opacity, double opacity2):
    cdef int i, j, cur_idx
    cdef double cur
    cdef int image_width = src_img.size[0]
    cdef int image_height = src_img.size[1]

    cdef unsigned char[:] src = array.array("B", src_img.tobytes())
    cdef unsigned char[:] dst = array.array("B", dst_img.tobytes())

    i = 0
    while i < image_width:
        j = 0

        while j < image_height:
            cur_idx = (i * 4) + (j * (image_width * 4))

            if src[cur_idx + 3] == 0:
                j += 1
                continue

            cur = src[cur_idx + 0] * (src[cur_idx + 3] / 255.0) * opacity + dst[cur_idx + 0] * (dst[cur_idx + 3] / 255.0) * opacity2
            dst[cur_idx + 0] = 255 if cur > 255 else int(cur)

            cur = src[cur_idx + 1] * (src[cur_idx + 3] / 255.0) * opacity + dst[cur_idx + 1] * (dst[cur_idx + 3] / 255.0) * opacity2
            dst[cur_idx + 1] = 255 if cur > 255 else int(cur)

            cur = src[cur_idx + 2] * (src[cur_idx + 3] / 255.0) * opacity + dst[cur_idx + 2] * (dst[cur_idx + 3] / 255.0) * opacity2
            dst[cur_idx + 2] = 255 if cur > 255 else int(cur)

            cur = src[cur_idx + 3] * (src[cur_idx + 3] / 255.0) * opacity + dst[cur_idx + 3] * (dst[cur_idx + 3] / 255.0) * opacity2
            dst[cur_idx + 3] = 255 if cur > 255 else int(cur)

            j += 1
        i += 1

    dst_new = Image.frombytes(dst_img.mode, dst_img.size, bytes(dst))
    dst_img.close()
    del dst_img

    return dst_new
