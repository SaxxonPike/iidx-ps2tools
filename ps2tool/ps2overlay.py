import ctypes
import os
import struct

from PIL import Image, ImageOps
import blowfish

import common

def read_frames_from_ifs(filename):
    data = open(filename, "rb").read()

    file_offsets = []

    img_start_idx = struct.unpack("<I", data[0x04:0x08])[0]

    data_idx = 0x0c
    while True:
        file_offset = struct.unpack("<I", data[data_idx:data_idx + 4])[0]
        data_idx += 4

        if file_offset == 0xffffffff:
            break

        file_offsets.append(file_offset * 4)

    overlay_images = {}
    for offset in file_offsets:
        raw_data = bytes(common.decode_lz(data[offset+4:]))

        new_raw_data = bytearray()

        for b in raw_data:
            new_raw_data.append(b & 0x0f)
            new_raw_data.append((b & 0xf0) >> 4)

        raw_data = bytes(new_raw_data)
        overlay_images[img_start_idx] = Image.frombytes('P', (128, 128), raw_data)

        img_start_idx += 1

    return overlay_images


def extract_overlay(exe_filename, ifs_filename, palette_idx, overlay_id, output_filename, overlay_exe_offsets):
    exe = bytearray(open(exe_filename, "rb").read())

    palette_offset = struct.unpack("<I", exe[overlay_exe_offsets['palette_table']+(palette_idx*4):overlay_exe_offsets['palette_table']+(palette_idx*4)+4])[0] - overlay_exe_offsets['base_offset']
    palette_data = common.decode_lz(exe[palette_offset:])

    # Create palettes
    palettes = []
    for i in range(len(palette_data) // 2 // 16):
        cur_palette = []

        for j in range(16):
            c = struct.unpack("<H", palette_data[(i*16*2) + (j*2):(i*16*2) + (j*2)+2])[0]
            r = ((c & 0x7c00) >> 10) << 3
            g = ((c & 0x3e0) >> 5) << 3
            b = (c & 0x1F) << 3
            cur_palette.append((r, g, b))

        palettes.append(cur_palette)

    animation_id, frame_count = struct.unpack("<HH", exe[overlay_exe_offsets['animation_table']+(overlay_id * 4):overlay_exe_offsets['animation_table']+(overlay_id * 4)+4])
    animation_parts_data = exe[overlay_exe_offsets['animation_data_table']+(animation_id*10):overlay_exe_offsets['animation_data_table']+(animation_id*10)+((frame_count)*10)]

    animation_parts = []
    for i in range(len(animation_parts_data) // 10):
        idx, anim_len, _, w, h, unk = struct.unpack("<HBBHHH", animation_parts_data[i * 10:(i * 10) + 10])

        if anim_len == 0xff:
            continue

        animation_parts.append((idx, anim_len))

    sprites = []

    for idx, anim_len in animation_parts:
        cur_frame = []

        for i2 in range(1):
            idx2, size = struct.unpack("<HH", exe[overlay_exe_offsets['animation_parts_table'] + ((idx + i2) * 4):overlay_exe_offsets['animation_parts_table'] + ((idx + i2) * 4) + 4])

            for i in range(size):
                t = 0
                dst_x, dst_y, src_w, src_h, img_idx, src_x, src_y, palette, rotation, unk2 = struct.unpack("<HHHHHBBBBH", exe[overlay_exe_offsets['tile_table'] - t + ((idx2 + i) * 16):overlay_exe_offsets['tile_table'] - t + ((idx2 + i) * 16) + 16])

                dst_x = ctypes.c_short(dst_x).value
                dst_y = ctypes.c_short(dst_y).value
                src_w = ctypes.c_short(src_w).value
                src_h = ctypes.c_short(src_h).value
                src_x = ctypes.c_short(src_x).value
                src_y = ctypes.c_short(src_y).value

                cur_frame.append({
                    'dst_x': dst_x,
                    'dst_y': dst_y,
                    'src_w': src_w,
                    'src_h': src_h,
                    'img_idx': img_idx,
                    'src_x': src_x,
                    'src_y': src_y,
                    'palette': palette,
                    'rotation': rotation,
                    'unk2': unk2,
                })

        sprites.append(cur_frame)

    overlay_images = read_frames_from_ifs(ifs_filename)

    frames = []
    idx = 0
    for sprite_parts in sprites:
        output = Image.new('RGBA', (512, 512))

        for sprite in sprite_parts:
            crop_region = (sprite['src_x'], sprite['src_y'], sprite['src_x'] + sprite['src_w'], sprite['src_y'] + sprite['src_h'])
            dst_region = (sprite['dst_x'], sprite['dst_y'], sprite['dst_x'] + sprite['src_w'], sprite['dst_y'] + sprite['src_h'])
            src_img = overlay_images[sprite['img_idx']].crop(crop_region)

            palette = []

            trans_color = palettes[sprite['palette']][0]

            for color in palettes[sprite['palette']]:
                palette.append(color[2])
                palette.append(color[1])
                palette.append(color[0])

            src_img.putpalette(palette)

            src_img = src_img.convert("RGBA")
            datas = src_img.getdata()

            newData = []
            for item in datas:
                if item[0] == trans_color[2] and item[1] == trans_color[1] and item[2] == trans_color[0]:
                    newData.append((255, 255, 255, 0))
                else:
                    newData.append(item)

            src_img.putdata(newData)

            if (sprite['rotation'] & 0x01) == 1:
                src_img = ImageOps.flip(src_img)

            if (sprite['rotation'] & 0x02) == 2:
                src_img = ImageOps.mirror(src_img)

            if sprite['rotation'] not in [0, 1, 2, 3]:
                print("Found known rotation flag:", sprite['rotation'])

            output.paste(src_img, dst_region, src_img.convert("RGBA"))

        frames.append(output.crop((171, 0, 469, 208)).copy())

    if len(frames) > 0:
        frames[0].save('{}.gif'.format(output_filename), save_all=True, append_images=frames[1:], loop=0xffff, disposal=2)
