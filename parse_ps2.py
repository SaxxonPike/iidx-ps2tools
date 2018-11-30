import ctypes
import os
import struct

from PIL import Image, ImageOps
import blowfish

overlay_offsets = {
    'slpm_657.68': { # 8th
        'base_offset': 0xfff80,

        'palette_table': 0x124a20,
        'animation_table': 0x124ba0,
        'animation_data_table': 0x127480,
        'tile_table': 0x136f10,
        'animation_parts_table': 0x191bd0,
    },
    'slpm_655.93': { # 7th
        'base_offset': 0xfff80,

        'palette_table': 0xf66b0,
        'animation_table': 0xf68d0,
        'animation_data_table': 0xfa9a0,
        'tile_table': 0x111610,
        'animation_parts_table': 0x1aec50,
    },
    'slpm_651.56': { # 6th
        'base_offset': 0xff000,

        'palette_table': 0x171138,
        'animation_table': 0xd1dc4,
        'animation_data_table': 0xd63a8,
        'tile_table': 0xeb3d8,
        'animation_parts_table': 0x15e298,
    },
    'slpm_650.49': { # 5th
        'base_offset': 0xff000,

        'palette_table': 0x174828,
        'animation_table': 0xb44a8,
        'animation_data_table': 0xb9608,
        'tile_table': 0xd2c70,
        'animation_parts_table': 0x163190,
    },
    'slpm_650.26': { # 4th
        'base_offset': 0xff000,

        'palette_table': 0x12b4f0,
        'animation_table': 0x8e108,
        'animation_data_table': 0x91640,
        'tile_table': 0xa6a80,
        'animation_parts_table': 0x11ec50,
    },
    'slpm_650.06': { # 3rd
        'base_offset': 0xff000,

        'palette_table': 0x13d128,
        'animation_table': 0x7ac70,
        'animation_data_table': 0x7df48,
        'tile_table': 0x94ff8,
        'animation_parts_table': 0x130ac8,
    },
}

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
        raw_data = bytes(decode_lz(data[offset+4:]))

        new_raw_data = bytearray()

        for b in raw_data:
            new_raw_data.append(b & 0x0f)
            new_raw_data.append((b & 0xf0) >> 4)

        raw_data = bytes(new_raw_data)
        overlay_images[img_start_idx] = Image.frombytes('P', (128, 128), raw_data)

        img_start_idx += 1

    return overlay_images

def extract_overlay(exe_filename, ifs_filename, palette_idx, overlay_id, output_filename):
    if exe_filename.lower() not in overlay_offsets:
        return

    overlay_exe_offsets = overlay_offsets[exe_filename.lower()]

    exe = bytearray(open(exe_filename, "rb").read())

    palette_offset = struct.unpack("<I", exe[overlay_exe_offsets['palette_table']+(palette_idx*4):overlay_exe_offsets['palette_table']+(palette_idx*4)+4])[0] - overlay_exe_offsets['base_offset']
    palette_data = decode_lz(exe[palette_offset:])

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


CHUNK_SIZE = 0x800

DIFFICULTY_MAPPING = {
    0: 'SP HYPER',
    1: 'DP HYPER',
    2: 'SP ANOTHER',
    3: 'DP ANOTHER',
    4: 'SP NORMAL',
    5: 'DP NORMAL',
    6: 'SP BEGINNER',
    7: 'DP BEGINNER', # Never used?
}

def read_string(infile, offset):
    cur_offset = infile.tell()

    infile.seek(offset)

    string = []
    while True:
        c = infile.read(1)

        if c == b'\0':
            break

        string.append(c)

    infile.seek(cur_offset)

    return b"".join(string).decode('shift-jis')


def generate_encryption_key_gold():
    key_parts = [
        "FIRE FIRE", # b0 0
        "Blind Justice", # b4 1
        "earth-like planet", # b8 2
        "2hot2eat", # bc 3
        "op.31", # c0 4
        "X-rated", # c4 5
        "Sense 2007", # c8 6
        "Cyber Force", # cc 7
        "ANDROMEDA II", # d0 8
        "heaven above", # d4 9
    ]

    key = ""
    key += key_parts[1][8]
    key += key_parts[0][3]
    key += key_parts[2][8]
    key += key_parts[3][4]
    key += key_parts[0][1]
    key += key_parts[4][4]
    key += key_parts[5][0]
    key += 'q'
    key += key_parts[6][9]
    key += key_parts[7][2]
    key += 'z'
    key += key_parts[6][8]
    key += '9'
    key += key_parts[8][5]
    key += key_parts[1][9]
    key += key_parts[9][3]

    return key


def generate_encryption_key_djtroopers():
    key_parts = [
        "Blue Rain", # 70 0
        "oratio", # 74 1
        "Digitank System", # 78 2
        "four pieces of heaven", # 7c 3
        "2 tribe 4 K", # 80 4
        "end of world", # 84 5
        "Darling my LUV", # 88 6
        "MENDES", # 8c 7
        "TRIP MACHINE PhoeniX", # 90 8
        "NEW GENERATION", # 94 9
    ]

    key = ""
    key += key_parts[0][3]
    key += 'q'
    key += key_parts[2][7]
    key += key_parts[0][0]
    key += key_parts[0][7]
    key += key_parts[3][5]
    key += 'x'
    key += key_parts[4][0]
    key += key_parts[5][7]
    key += key_parts[6][6]
    key += key_parts[7][1]
    key += 'x'
    key += key_parts[6][12]
    key += key_parts[8][6]
    key += key_parts[8][9]
    key += key_parts[9][4]

    return key


def generate_encryption_key_empress():
    key_parts = [
        "PERFECT FULL COMBO HARD EASY", # c0 0
        "ASSIST CLEAR PLAY", # c4 1
        "RANDOM MIRROR", # c8 2
        "Auto Scratch 5Keys", # cc 3
        "DOUBLE BATTLE Win Lose", # d0 4
        "Hi-Speed Flip", # d4 5
        "Normal Hyper Another", # d8 6
        "Beginner Tutorial", # dc 7
        "ECHO REVERB EQ ONLY", # e0 8
        "STANDARD EXPERT CLASS", # e4 9
    ]

    key = ""
    key += key_parts[7][10]
    key += key_parts[8][18]
    key += key_parts[5][10]
    key += key_parts[0][3]
    key += key_parts[7][2]
    key += key_parts[8][7]
    key += 'w'
    key += key_parts[2][4]
    key += key_parts[5][4]
    key += key_parts[3][8]
    key += key_parts[8][13]
    key += key_parts[6][3]
    key += key_parts[9][10]
    key += key_parts[5][7]
    key += key_parts[1][3]
    key += key_parts[1][11]

    return key


def decode_lz(input_data):
    # Based on decompression code from IIDX GOLD CS
    input_data = bytearray(input_data)
    idx = 0

    output = bytearray()

    control = 0
    while True:
        control >>= 1

        if (control & 0x100) == 0:
            control = input_data[idx] | 0xff00
            idx += 1

        data = input_data[idx]
        idx += 1

        if (control & 1) == 0:
            output.append(data)
            continue

        length = None
        if (data & 0x80) == 0:
            distance = ((data & 0x03) << 8) | input_data[idx]
            length = (data >> 2) + 2
            idx += 1

        elif (data & 0x40) == 0:
            distance = (data & 0x0f) + 1
            length = (data >> 4) - 7

        if length is not None:
            start_offset = len(output)
            idx2 = 0

            while idx2 <= length:
                output.append(output[(start_offset - distance) + idx2])
                idx2 += 1

            continue

        if data == 0xff:
            break

        length = data - 0xb9
        while length >= 0:
            output.append(input_data[idx])
            idx += 1
            length -= 1

    return output


def decrypt_blowfish(data, key):
    if len(data) % 8 == 0:
        data += bytearray([0] * 8)

    cipher = blowfish.Cipher(key.encode('ascii'), byte_order="little")
    return bytearray(b"".join(cipher.decrypt_cbc_cts(data, bytearray([0] * 8))))


def get_sanitized_filename(filename, invalid_chars='<>:;\"\\/|?*'):
    for c in invalid_chars:
        filename = filename.replace(c, "_")

    return filename


# Generic extraction code
def extract_file(filename, table, index, output_folder, output_filename):
    entry = table[index] if index < len(table) else None

    gif_output_filename = output_filename.replace(".if", "")

    if entry is None:
        return

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    with open(filename, "rb") as infile:
        print("Extracting", output_filename)

        infile.seek(entry['offset'])
        data = infile.read(entry['size'])

        if entry.get('encryption', None) is not None:
            data = decrypt_blowfish(data, entry['encryption'])

        if entry.get('compression', None) is not None:
            data = entry['compression'](data)

        output_filename = os.path.join(output_folder, get_sanitized_filename(output_filename))
        open(output_filename, "wb").write(data)

        if entry.get('overlays', None) is not None:
            for overlay_idx in entry['overlays']['indexes']:
                extract_overlay(entry['overlays']['exe'], output_filename, entry['overlays']['palette'], overlay_idx, get_sanitized_filename("%s [%04x]" % (gif_output_filename, overlay_idx)))

def filetable_reader_modern(executable_filename, filename, offset, file_count):
    file_entries = []

    with open(executable_filename, "rb") as infile:
        infile.seek(offset)

        for i in range(file_count):
            offset, size = struct.unpack("<II", infile.read(8))

            offset *= CHUNK_SIZE
            size *= CHUNK_SIZE

            file_entries.append({
                'real_filename': [],
                'filename': filename,
                'offset': offset,
                'size': size,
            })

    return file_entries


def filetable_reader_modern2(executable_filename, filename, offset, file_count):
    file_entries = []

    with open(executable_filename, "rb") as infile:
        infile.seek(offset)

        for i in range(file_count):
            offset, _, size = struct.unpack("<III", infile.read(12))

            offset *= CHUNK_SIZE

            file_entries.append({
                'real_filename': [],
                'filename': filename,
                'offset': offset,
                'size': size,
            })

    return file_entries


def filetable_reader_3rd(executable_filename, filename, offset, file_count):
    file_entries = []

    with open(executable_filename, "rb") as infile:
        infile.seek(offset)

        for i in range(file_count):
            offset, size, hash = struct.unpack("<III", infile.read(12))

            offset *= CHUNK_SIZE

            file_entries.append({
                'real_filename': [],
                'filename': filename,
                'offset': offset,
                'size': size,
            })

    return file_entries


def filetable_reader_8th(executable_filename, filename, offset, file_count):
    file_entries = []

    with open(executable_filename, "rb") as infile:
        infile.seek(offset)

        for i in range(0, file_count):
            offset, _, size, hash = struct.unpack("<IIII", infile.read(16))

            offset *= CHUNK_SIZE

            file_entries.append({
                'real_filename': [],
                'filename': filename,
                'offset': offset,
                'size': size,
            })

    return file_entries


def parse_file(executable_filename, filename, offset, file_count, output_folder, extract=True, filetable_reader=None):
    if filetable_reader is None:
        filetable_reader = FILETABLE_READERS[executable_filename.lower()] if executable_filename.lower() in FILETABLE_READERS else None

    if filetable_reader is None:
        print("Couldn't find file table reader for", executable_filename)
        return []

    file_entries = filetable_reader(executable_filename, filename, offset, file_count)

    if extract:
        for i in range(len(file_entries)):
            extract_file(filename, file_entries, i, output_folder, "file_%04d.bin" % i)

    return file_entries


# Songlist code
def songlist_reader_happysky(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x144, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x14, 1)
            videos_idx = struct.unpack("<II", infile.read(8))

            infile.seek(0x90, 1)
            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            for index, file_index in enumerate(videos_idx):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%d].mpg" % (title, index))

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['compression'] = decode_lz

            sound_pairs = [
                [sounds_idx[0], sounds_idx[2]],
                [sounds_idx[1], sounds_idx[3]],
                [sounds_idx[4], sounds_idx[6]],
                [sounds_idx[5], sounds_idx[7]],
                [sounds_idx[8], sounds_idx[10]],
                [sounds_idx[9], sounds_idx[11]],
                [sounds_idx[12], sounds_idx[14]],
                [sounds_idx[13], sounds_idx[15]]
            ]

            for pair_index, pair in enumerate(sound_pairs):
                for index, file_index in enumerate(pair):
                    is_keysound = index == 0

                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    if is_keysound:
                        file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, pair_index))
                    else:
                        file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, pair_index))

    return file_entries

def songlist_reader_9th(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x16c, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x18, 1)
            videos_idx = struct.unpack("<II", infile.read(8))

            infile.seek(0xcc, 1)
            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            for index, file_index in enumerate(videos_idx):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%d].mpg" % (title, index))

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['compression'] = decode_lz

            sound_pairs = [
                [sounds_idx[0], sounds_idx[2]],
                [sounds_idx[1], sounds_idx[3]],
                [sounds_idx[4], sounds_idx[6]],
                [sounds_idx[5], sounds_idx[7]],
                [sounds_idx[8], sounds_idx[10]],
                [sounds_idx[9], sounds_idx[11]],
                [sounds_idx[12], sounds_idx[14]],
                [sounds_idx[13], sounds_idx[15]]
            ]

            for pair_index, pair in enumerate(sound_pairs):
                for index, file_index in enumerate(pair):
                    is_keysound = index == 0

                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    if is_keysound:
                        file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, pair_index))
                    else:
                        file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, pair_index))

    return file_entries


def songlist_reader_red(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x140, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x1c, 1)
            videos_idx = struct.unpack("<II", infile.read(8))

            infile.seek(0x9c, 1)
            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            for index, file_index in enumerate(videos_idx):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%d].mpg" % (title, index))

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['compression'] = decode_lz

            sound_pairs = [
                [sounds_idx[0], sounds_idx[2]],
                [sounds_idx[1], sounds_idx[3]],
                [sounds_idx[4], sounds_idx[6]],
                [sounds_idx[5], sounds_idx[7]],
                [sounds_idx[8], sounds_idx[10]],
                [sounds_idx[9], sounds_idx[11]],
                [sounds_idx[12], sounds_idx[14]],
                [sounds_idx[13], sounds_idx[15]]
            ]

            for pair_index, pair in enumerate(sound_pairs):
                for index, file_index in enumerate(pair):
                    is_keysound = index == 0

                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    if is_keysound:
                        file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, pair_index))
                    else:
                        file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, pair_index))

    return file_entries


def songlist_reader_distorted(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x118, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x14, 1)
            videos_idx = struct.unpack("<II", infile.read(8))

            infile.seek(0x5c, 1)
            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            for index, file_index in enumerate(videos_idx):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%d].mpg" % (title, index))

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['compression'] = decode_lz

            sound_pairs = [
                [sounds_idx[0], sounds_idx[2]],
                [sounds_idx[1], sounds_idx[3]],
                [sounds_idx[4], sounds_idx[6]],
                [sounds_idx[5], sounds_idx[7]],
                [sounds_idx[8], sounds_idx[10]],
                [sounds_idx[9], sounds_idx[11]],
                [sounds_idx[12], sounds_idx[14]],
                [sounds_idx[13], sounds_idx[15]]
            ]

            for pair_index, pair in enumerate(sound_pairs):
                for index, file_index in enumerate(pair):
                    is_keysound = index == 0

                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    if is_keysound:
                        file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, pair_index))
                    else:
                        file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, pair_index))

    return file_entries

def songlist_reader_gold(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x11c, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x14, 1)
            videos_idx = struct.unpack("<II", infile.read(8))

            infile.seek(0x58, 1)
            charts_idx = struct.unpack("<IIIIIIIIII", infile.read(0x28)) # 28??
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            for index, file_index in enumerate(videos_idx):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%d].mpg" % (title, index))

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['encryption'] = generate_encryption_key_gold()
                file_entries[file_index]['compression'] = decode_lz

            sound_pairs = [
                [sounds_idx[0], sounds_idx[2]],
                [sounds_idx[1], sounds_idx[3]],
                [sounds_idx[4], sounds_idx[6]],
                [sounds_idx[5], sounds_idx[7]],
                [sounds_idx[8], sounds_idx[10]],
                [sounds_idx[9], sounds_idx[11]],
                [sounds_idx[12], sounds_idx[14]],
                [sounds_idx[13], sounds_idx[15]]
            ]

            for pair_index, pair in enumerate(sound_pairs):
                for index, file_index in enumerate(pair):
                    is_keysound = index == 0

                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    if is_keysound:
                        file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, pair_index))
                    else:
                        file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, pair_index))

    return file_entries


def songlist_reader_djtroopers(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x134, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x18, 1)
            videos_idx = struct.unpack("<II", infile.read(8))

            infile.seek(0x60, 1)
            charts_idx = struct.unpack("<IIIIIIIIII", infile.read(0x28)) # 28??
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            for index, file_index in enumerate(videos_idx):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%d].mpg" % (title, index))

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['encryption'] = generate_encryption_key_djtroopers()
                file_entries[file_index]['compression'] = decode_lz

            sound_pairs = [
                [sounds_idx[0], sounds_idx[2]],
                [sounds_idx[1], sounds_idx[3]],
                [sounds_idx[4], sounds_idx[6]],
                [sounds_idx[5], sounds_idx[7]],
                [sounds_idx[8], sounds_idx[10]],
                [sounds_idx[9], sounds_idx[11]],
                [sounds_idx[12], sounds_idx[14]],
                [sounds_idx[13], sounds_idx[15]]
            ]

            for pair_index, pair in enumerate(sound_pairs):
                for index, file_index in enumerate(pair):
                    is_keysound = index == 0

                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    if is_keysound:
                        file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, pair_index))
                    else:
                        file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, pair_index))

    return file_entries


def songlist_reader_empress(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x134, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x18, 1)
            videos_idx = struct.unpack("<II", infile.read(8))

            infile.seek(0x60, 1)
            charts_idx = struct.unpack("<IIIIIIIIII", infile.read(0x28)) # 28??
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            for index, file_index in enumerate(videos_idx):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%d].mpg" % (title, index))

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['encryption'] = generate_encryption_key_empress()
                file_entries[file_index]['compression'] = decode_lz

            sound_pairs = [
                [sounds_idx[0], sounds_idx[2]],
                [sounds_idx[1], sounds_idx[3]],
                [sounds_idx[4], sounds_idx[6]],
                [sounds_idx[5], sounds_idx[7]],
                [sounds_idx[8], sounds_idx[10]],
                [sounds_idx[9], sounds_idx[11]],
                [sounds_idx[12], sounds_idx[14]],
                [sounds_idx[13], sounds_idx[15]]
            ]

            for pair_index, pair in enumerate(sound_pairs):
                for index, file_index in enumerate(pair):
                    is_keysound = index == 0

                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    if is_keysound:
                        file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, pair_index))
                    else:
                        file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, pair_index))

    return file_entries


def songlist_reader_beatmaniaus(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x174, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x1c, 1)
            video_idx = struct.unpack("<I", infile.read(4))[0]

            infile.seek(0xd0, 1)
            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            file_entries[video_idx]['real_filename'].append("%s.mpg" % title)

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['compression'] = decode_lz

            sound_pairs = [
                [sounds_idx[0], sounds_idx[2]],
                [sounds_idx[1], sounds_idx[3]],
                [sounds_idx[4], sounds_idx[6]],
                [sounds_idx[5], sounds_idx[7]],
                [sounds_idx[8], sounds_idx[10]],
                [sounds_idx[9], sounds_idx[11]],
                [sounds_idx[12], sounds_idx[14]],
                [sounds_idx[13], sounds_idx[15]]
            ]

            for pair_index, pair in enumerate(sound_pairs):
                for index, file_index in enumerate(pair):
                    is_keysound = index == 0

                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    if is_keysound:
                        file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, pair_index))
                    else:
                        file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, pair_index))

    return file_entries


def songlist_reader_3rd(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        chart_data_buffer = infile.read()

        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x7c, 0)

            internal_title_offset, title_offset = struct.unpack("<II", infile.read(8))

            internal_title = read_string(infile, internal_title_offset - 0xff000)
            title = read_string(infile, title_offset - 0xff000)

            infile.seek(0x02, 1)
            video_idx = struct.unpack("<H", infile.read(2))[0]
            video_idx2 = video_idx + 1

            infile.seek(0x1c, 1)
            overlay_palette = struct.unpack("<H", infile.read(2))[0]

            infile.seek(0x0a, 1)
            overlay_idxs = []
            for i in range(0x1e // 6):
                overlay_type, overlay_idx, unk = struct.unpack("<HHH", infile.read(6))

                if overlay_type != 0:
                    overlay_idxs.append(overlay_idx)

            infile.seek(0x02, 1)

            charts_idx = struct.unpack("<IIIIII", infile.read(0x18))
            sounds_idx = struct.unpack("<HH", infile.read(0x04))
            bgm_idx = struct.unpack("<HHH", infile.read(0x06))
            overlay_idx = struct.unpack("<H", infile.read(0x02))[0]

            if video_idx not in [0xffff, 0x00]:
                file_entries[video_idx]['real_filename'].append("%s [0].mpg" % title)
                file_entries[video_idx+1]['real_filename'].append("%s [1].mpg" % title)

            if overlay_idx not in [0xffff, 0x00]:
                overlay_filename = "%s.if" % title
                file_entries[overlay_idx]['real_filename'].append(overlay_filename)
                file_entries[overlay_idx]['overlays'] = {
                    'exe': executable_filename,
                    'palette': overlay_palette,
                    'indexes': overlay_idxs
                }

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                output_filename = os.path.join(output_folder, get_sanitized_filename("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index)))))

                print("Extracting", output_filename)

                open(output_filename, "wb").write(decode_lz(chart_data_buffer[file_index-0xff000:]))

            for index, file_index in enumerate(sounds_idx):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, index))

            for index, file_index in enumerate(bgm_idx):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, index))

    return file_entries


def songlist_reader_4th(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        chart_data_buffer = infile.read()

        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x90, 0)

            internal_title_offset, title_offset = struct.unpack("<II", infile.read(8))

            internal_title = read_string(infile, internal_title_offset - 0xff000)
            title = read_string(infile, title_offset - 0xff000)

            infile.seek(0x06, 1)
            video_idx = struct.unpack("<H", infile.read(2))[0]
            video_idx2 = video_idx + 1

            infile.seek(0x1c, 1)
            overlay_palette = struct.unpack("<H", infile.read(2))[0]

            infile.seek(0x0a, 1)
            overlay_idxs = []
            for i in range(0x1e // 6):
                overlay_type, overlay_idx, unk = struct.unpack("<HHH", infile.read(6))

                if overlay_type != 0:
                    overlay_idxs.append(overlay_idx)

            infile.seek(0x02, 1)

            charts_idx = struct.unpack("<IIIIII", infile.read(0x18))
            sounds_idx_1 = struct.unpack("<HH", infile.read(0x04))
            bgms_idx_1 = struct.unpack("<HHHHHH", infile.read(0x0c))
            sounds_idx_2 = struct.unpack("<HH", infile.read(0x04))
            bgms_idx_2 = struct.unpack("<HH", infile.read(0x04))
            overlay_idx = struct.unpack("<H", infile.read(0x02))[0]

            if video_idx not in [0xffff, 0x00]:
                file_entries[video_idx]['real_filename'].append("%s [0].mpg" % title)
                file_entries[video_idx+1]['real_filename'].append("%s [1].mpg" % title)

            if overlay_idx not in [0xffff, 0x00]:
                overlay_filename = "%s.if" % title
                file_entries[overlay_idx]['real_filename'].append(overlay_filename)
                file_entries[overlay_idx]['overlays'] = {
                    'exe': executable_filename,
                    'palette': overlay_palette,
                    'indexes': overlay_idxs
                }

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                output_filename = os.path.join(output_folder, get_sanitized_filename("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index)))))

                print("Extracting", output_filename)

                open(output_filename, "wb").write(decode_lz(chart_data_buffer[file_index-0xff000:]))

            for index, file_index in enumerate(sounds_idx_1):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [0-%d].wvb" % (title, index))

            for index, file_index in enumerate(bgms_idx_1):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [0-%d].pcm" % (title, index))

            for index, file_index in enumerate(sounds_idx_2):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [1-%d].wvb" % (title, index))

            for index, file_index in enumerate(bgms_idx_2):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                print("%08x" % infile.tell(), file_index, len(file_entries))

                file_entries[file_index]['real_filename'].append("%s [1-%d].pcm" % (title, index))

    return file_entries


def songlist_reader_5th(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        chart_data_buffer = infile.read()

        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0xa4, 0)

            internal_title_offset, title_offset = struct.unpack("<II", infile.read(8))

            internal_title = read_string(infile, internal_title_offset - 0xff000)
            title = read_string(infile, title_offset - 0xff000)

            infile.seek(0x0a, 1)
            video_idx = struct.unpack("<H", infile.read(2))[0]
            video_idx2 = video_idx + 1

            infile.seek(0x18, 1)
            overlay_palette = struct.unpack("<H", infile.read(2))[0]

            infile.seek(0x0e, 1)
            overlay_idxs = []
            for i in range(0x1e // 6):
                overlay_type, overlay_idx, unk = struct.unpack("<HHH", infile.read(6))

                if overlay_type != 0:
                    overlay_idxs.append(overlay_idx)

            infile.seek(0x02, 1)

            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))
            overlay_idx = struct.unpack("<H", infile.read(0x02))[0]

            if video_idx not in [0xffff, 0x00]:
                file_entries[video_idx]['real_filename'].append("%s [0].mpg" % title)
                file_entries[video_idx+1]['real_filename'].append("%s [1].mpg" % title)

            if overlay_idx not in [0xffff, 0x00]:
                overlay_filename = "%s.if" % title
                file_entries[overlay_idx]['real_filename'].append(overlay_filename)
                file_entries[overlay_idx]['overlays'] = {
                    'exe': executable_filename,
                    'palette': overlay_palette,
                    'indexes': overlay_idxs
                }

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                output_filename = os.path.join(output_folder, get_sanitized_filename("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index)))))

                print("Extracting", output_filename)

                open(output_filename, "wb").write(decode_lz(chart_data_buffer[file_index-0xff000:]))

            sound_pairs = [
                [sounds_idx[0], sounds_idx[2]],
                [sounds_idx[1], sounds_idx[3]],
                [sounds_idx[4], sounds_idx[6]],
                [sounds_idx[5], sounds_idx[7]],
                [sounds_idx[8], sounds_idx[10]],
                [sounds_idx[9], sounds_idx[11]],
                [sounds_idx[12], sounds_idx[14]],
                [sounds_idx[13], sounds_idx[15]]
            ]

            for pair_index, pair in enumerate(sound_pairs):
                for index, file_index in enumerate(pair):
                    is_keysound = index == 0

                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    if is_keysound:
                        file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, pair_index))
                    else:
                        file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, pair_index))

    return file_entries


def songlist_reader_6th(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        chart_data_buffer = infile.read()

        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0xa0, 0)

            internal_title_offset, title_offset = struct.unpack("<II", infile.read(8))

            internal_title = read_string(infile, internal_title_offset - 0xff000)
            title = read_string(infile, title_offset - 0xff000)

            infile.seek(0x12, 1)
            video_idx2 = struct.unpack("<H", infile.read(2))[0]

            infile.seek(0x0c, 1)
            video_idx = struct.unpack("<H", infile.read(2))[0]

            infile.seek(0x0a, 1)
            overlay_palette = struct.unpack("<H", infile.read(2))[0]

            infile.seek(0x0c, 1)
            overlay_idxs = []
            for i in range(0x16 // 4):
                overlay_type, overlay_idx = struct.unpack("<HH", infile.read(4))

                if overlay_type != 0:
                    overlay_idxs.append(overlay_idx)

            infile.seek(0x02, 1)

            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))
            overlay_idx = struct.unpack("<H", infile.read(0x02))[0]

            if overlay_idx not in [0xffff, 0x00]:
                overlay_filename = "%s.if" % title
                file_entries[overlay_idx]['real_filename'].append(overlay_filename)
                file_entries[overlay_idx]['overlays'] = {
                    'exe': executable_filename,
                    'palette': overlay_palette,
                    'indexes': overlay_idxs
                }

            if video_idx not in [0xffff, 0x00]:
                file_entries[video_idx]['real_filename'].append("%s [0].mpg" % title)

            if video_idx2 not in [0xffff, 0x00]:
                file_entries[video_idx2]['real_filename'].append("%s [1].mpg" % title)

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                output_filename = os.path.join(output_folder, get_sanitized_filename("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index)))))

                print("Extracting", output_filename)

                open(output_filename, "wb").write(decode_lz(chart_data_buffer[file_index-0xff000:]))

            sound_pairs = [
                [sounds_idx[0], sounds_idx[2]],
                [sounds_idx[1], sounds_idx[3]],
                [sounds_idx[4], sounds_idx[6]],
                [sounds_idx[5], sounds_idx[7]],
                [sounds_idx[8], sounds_idx[10]],
                [sounds_idx[9], sounds_idx[11]],
                [sounds_idx[12], sounds_idx[14]],
                [sounds_idx[13], sounds_idx[15]]
            ]

            for pair_index, pair in enumerate(sound_pairs):
                for index, file_index in enumerate(pair):
                    is_keysound = index == 0

                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    if is_keysound:
                        file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, pair_index))
                    else:
                        file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, pair_index))

    return file_entries


def songlist_reader_7th(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        chart_data_buffer = infile.read()

        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0xa0, 0)

            internal_title_offset, title_offset = struct.unpack("<II", infile.read(8))

            internal_title = read_string(infile, internal_title_offset - 0xfff80)
            title = read_string(infile, title_offset - 0xfff80)

            infile.seek(0x12, 1)
            video_idx = struct.unpack("<H", infile.read(2))[0]

            infile.seek(0x0c, 1)
            video_idx2 = struct.unpack("<H", infile.read(2))[0]

            if video_idx == 0xffff:
                video_idx = video_idx2

            infile.seek(0x0a, 1)
            overlay_palette = struct.unpack("<H", infile.read(2))[0]

            infile.seek(0x0c, 1)

            overlay_idxs = []

            for i in range(0x16 // 4):
                overlay_type, overlay_idx = struct.unpack("<HH", infile.read(4))

                if overlay_type != 0:
                    overlay_idxs.append(overlay_idx)

            infile.seek(2, 1)

            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))
            overlay_idx = struct.unpack("<H", infile.read(0x02))[0]

            if video_idx not in [0xffff, 0x00]:
                if video_idx >= 138:
                    video_idx += 138

                file_entries[video_idx]['real_filename'].append("%s.mpg" % title)

            if overlay_idx not in [0xffff, 0x00]:
                if overlay_idx >= 138:
                    overlay_idx += 138

                overlay_filename = "%s.if" % title
                file_entries[overlay_idx]['real_filename'].append(overlay_filename)
                file_entries[overlay_idx]['overlays'] = {
                    'exe': executable_filename,
                    'palette': overlay_palette,
                    'indexes': overlay_idxs
                }

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_index = (file_index & 0x0fffffff) + 138
                file_entries[file_index]['real_filename'].append("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['compression'] = decode_lz

            sound_pairs = [
                [sounds_idx[0], sounds_idx[2]],
                [sounds_idx[1], sounds_idx[3]],
                [sounds_idx[4], sounds_idx[6]],
                [sounds_idx[5], sounds_idx[7]],
                [sounds_idx[8], sounds_idx[10]],
                [sounds_idx[9], sounds_idx[11]],
                [sounds_idx[12], sounds_idx[14]],
                [sounds_idx[13], sounds_idx[15]]
            ]

            for pair_index, pair in enumerate(sound_pairs):
                for index, file_index in enumerate(pair):
                    is_keysound = index == 0

                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    if file_index >= 138:
                        file_index += 138

                    if is_keysound:
                        file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, pair_index))
                    else:
                        file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, pair_index))

    return file_entries


def songlist_reader_8th(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    with open(executable_filename, "rb") as infile:
        chart_data_buffer = infile.read()

        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x9c, 0)

            internal_title_offset, title_offset = struct.unpack("<II", infile.read(8))

            internal_title = read_string(infile, internal_title_offset - 0xfff80)
            title = read_string(infile, title_offset - 0xfff80)

            infile.seek(0x0c, 1)
            videos_idx = struct.unpack("<HH", infile.read(4))

            infile.seek(0x18, 1)
            overlay_palette = struct.unpack("<H", infile.read(2))[0]

            infile.seek(0xc, 1)

            overlay_idxs = []

            for i in range(0x16 // 4):
                overlay_type, overlay_idx = struct.unpack("<HH", infile.read(4))

                if overlay_type != 0:
                    overlay_idxs.append(overlay_idx)

            infile.seek(2, 1)

            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))
            overlay_idx = struct.unpack("<H", infile.read(0x02))[0]

            for index, file_index in enumerate(videos_idx):
                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                if file_index >= 116:
                    file_index += 116

                file_entries[file_index]['real_filename'].append("%s [%d].mpg" % (title, index))

            if overlay_idx not in [0xffff, 0x00]:
                if overlay_idx >= 116:
                    overlay_idx += 116

                overlay_filename = "%s.if" % title
                file_entries[overlay_idx]['real_filename'].append(overlay_filename)
                file_entries[overlay_idx]['overlays'] = {
                    'exe': executable_filename,
                    'palette': overlay_palette,
                    'indexes': overlay_idxs
                }

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_index = (file_index & 0x0fffffff) + 116
                file_entries[file_index]['real_filename'].append("%s [%s].ply" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['compression'] = decode_lz

            sound_pairs = [
                [sounds_idx[0], sounds_idx[2]],
                [sounds_idx[1], sounds_idx[3]],
                [sounds_idx[4], sounds_idx[6]],
                [sounds_idx[5], sounds_idx[7]],
                [sounds_idx[8], sounds_idx[10]],
                [sounds_idx[9], sounds_idx[11]],
                [sounds_idx[12], sounds_idx[14]],
                [sounds_idx[13], sounds_idx[15]]
            ]

            for pair_index, pair in enumerate(sound_pairs):
                for index, file_index in enumerate(pair):
                    is_keysound = index == 0

                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    if file_index >= 116:
                        file_index += 116

                    if is_keysound:
                        file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, pair_index))
                    else:
                        file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, pair_index))

    return file_entries


def parse_songlist(executable_filename, file_entries, songlist_offset, songlist_count, output_folder):
    if songlist_offset is None or songlist_count is None:
        return file_entries

    songlist_reader = SONGLIST_READERS[executable_filename.lower()] if executable_filename.lower() in SONGLIST_READERS else None

    if songlist_reader is not None:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        return songlist_reader(executable_filename, file_entries, songlist_offset, songlist_count, output_folder)

    return file_entries


def parse_archives(executable_filename, archives, output_folder, songlist_offset=None, songlist_count=None):
    file_entries = []

    for archive in archives:
        file_entries += parse_file(executable_filename, archive['filename'], archive['offset'], archive['entries'], output_folder, extract=False)

    file_entries = parse_songlist(executable_filename, file_entries, songlist_offset, songlist_count, output_folder)

    for i in range(len(file_entries)):
        for real_filename in file_entries[i].get('real_filename', []):
            extract_file(file_entries[i]['filename'], file_entries, i, output_folder, real_filename)

        if len(file_entries[i].get('real_filename', [])) == 0:
            extract_file(file_entries[i]['filename'], file_entries, i, output_folder, "file_%04d.bin" % i)

    return file_entries


# Rivals code
def rivals_reader_happy_sky(executable_filename, file_entries, rivals_offset, rivals_count):
    # TODO: Research this more thoroughly
    with open(executable_filename, "rb") as infile:
        for i in range(rivals_count):
            infile.seek(rivals_offset + (i * 0x28), 0)
            title = infile.read(0x08).decode('shift-jis').strip('\0').strip()
            file_entries[i]['real_filename'].append("[%04d] %s.bin" % (i, title))

    return file_entries


def rivals_reader_distorted(executable_filename, file_entries, rivals_offset, rivals_count):
    # TODO: Research this more thoroughly
    with open(executable_filename, "rb") as infile:
        for i in range(rivals_count):
            infile.seek(rivals_offset + (i * 0x24), 0)
            title = infile.read(0x08).decode('shift-jis').strip('\0').strip()
            file_entries[i]['real_filename'].append("[%04d] %s.bin" % (i, title))

    return file_entries


def rivals_reader_empress(executable_filename, file_entries, rivals_offset, rivals_count):
    # TODO: Research this more thoroughly
    with open(executable_filename, "rb") as infile:
        for i in range(rivals_count):
            infile.seek(rivals_offset + (i * 0x0b), 0)
            title = infile.read(0x08).decode('shift-jis').strip('\0').strip()
            file_entries[i]['real_filename'].append("[%04d] %s.bin" % (i, title))

    return file_entries


def parse_rivals(executable_filename, archives, output_folder, rivals_offset, rivals_count, filetable_reader=None):
    file_entries = []

    for archive in archives:
        file_entries += parse_file(executable_filename, archive['filename'], archive['offset'], archive['entries'], output_folder, extract=False, filetable_reader=filetable_reader)

    rivals_reader = RIVALS_READERS[executable_filename.lower()] if executable_filename.lower() in RIVALS_READERS else None

    if rivals_reader is not None:
        file_entries = rivals_reader(executable_filename, file_entries, rivals_offset, rivals_count)

    for i in range(len(file_entries)):
        for real_filename in file_entries[i].get('real_filename', []):
            extract_file(file_entries[i]['filename'], file_entries, i, output_folder, real_filename)

        if len(file_entries[i].get('real_filename', [])) == 0:
            extract_file(file_entries[i]['filename'], file_entries, i, output_folder, "file_%04d.bin" % i)

    return file_entries


# DAT code
def dat_filetable_reader_modern(executable_filename, filename, offset, file_count):
    file_entries = []

    with open(executable_filename, "rb") as infile:
        infile.seek(offset)

        for i in range(file_count):
            fileid, offset, size, _ = struct.unpack("<IIII", infile.read(16))

            offset *= CHUNK_SIZE
            size *= CHUNK_SIZE

            file_entries.append({
                'real_filename': [],
                'filename': filename,
                'offset': offset,
                'size': size,
            })

    return file_entries


def parse_dats(executable_filename, archives, output_folder):
    dat_filetable_reader = DAT_FILETABLE_READERS[executable_filename.lower()] if executable_filename.lower() in DAT_FILETABLE_READERS else None

    if dat_filetable_reader is None:
        print("Couldn't find file table reader for", executable_filename)
        return []

    file_entries = []
    for archive in archives:
        file_entries += dat_filetable_reader(executable_filename, archive['filename'], archive['offset'], archive['entries'])

    for i in range(len(file_entries)):
        extract_file(file_entries[i]['filename'], file_entries, i, output_folder, "file_%04d.bin" % i)

    return file_entries


game_data = [
    {
        'title': 'beatmania IIDX 12 HAPPY SKY',
        'executable': 'SLPM_666.21',
        'data': [
            {
                'output': 'bm2dx12',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': "bm2dx12a.dat",
                        'offset': 0x105260,
                        'entries': 0xe0 // 8,
                    },
                    {
                        'filename': "bm2dx12b.dat",
                        'offset': 0x105340,
                        'entries': 0x1700 // 8,
                    },
                    {
                        'filename': "bm2dx12c.dat",
                        'offset': 0x106a40,
                        'entries': 0x458 // 8,
                    },
                ],
                'args': [
                    0x115f10,
                    0x7470 // 0x144
                ]
            },
            {
                'output': 'ROMRIVAL',
                'handler': parse_rivals,
                'archives': [
                    {
                        'filename': "ROMRIVAL.DAT",
                        'offset': 0x10a7d0,
                        'entries': 0x8d08 // 8,
                    }
                ],
                'args': [
                    0x12ccc0,
                    0x2c128 // 0x28
                ]
            },
            {
                'output': 'data1',
                'handler': parse_dats,
                'archives': [
                    {
                        'filename': "data1.dat",
                        'offset': 0x100108,
                        'entries': 0x1be0 // 16,
                    }
                ],
                'args': []
            }
        ],
    },
    {
        'title': 'beatmania US',
        'executable': 'SLUS_212.39',
        'data': [
            {
                'output': 'DATA1',
                'handler': parse_dats,
                'archives': [
                    {
                        'filename': "DATA1.DAT",
                        'offset': 0xb6ef0,
                        'entries': 0x790 // 16,
                    }
                ],
                'args': []
            },
            {
                'output': 'DATA2',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': "DATA2.DAT",
                        'offset': 0xba710,
                        'entries': 0x1230 // 8,
                    },
                ],
                'args': [
                    0xbf510,
                    0x6a14 // 0x174
                ]
            },
        ],
    },
    {
        'title': 'beatmania IIDX 3rd Style',
        'executable': 'SLPM_650.06',
        'data': [
            {
                'output': 'bm2dx3',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': os.path.join("DX2_3", "bm2dx3.bin"),
                        'offset': 0x145cd0,
                        'entries': 0x1050 // 12,
                    }
                ],
                'args': [
                    0x77fc8,
                    0x27b8 // 0x7c,
                ]
            },
        ],
    },
    {
        'title': 'beatmania IIDX 11th Style RED',
        'executable': 'SLPM_664.26',
        'data': [
            {
                'output': 'DATA1',
                'handler': parse_dats,
                'archives': [
                    {
                        'filename': "DATA1.DAT",
                        'offset': 0xe83e8,
                        'entries': 0x19c0 // 16,
                    }
                ],
                'args': []
            },
            {
                'output': 'DATA2',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': "DATA2.DAT",
                        'offset': 0xee440,
                        'entries': 0x1b40 // 8,
                    },
                ],
                'args': [
                    0x1c21f0,
                    0x6f40 // 0x140
                ]
            },
        ],
    },
    {
        'title': 'beatmania IIDX 13 DistorteD',
        'executable': 'SLPM_668.28',
        'data': [
            {
                'output': 'bm2dx13',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': "bm2dx13a.dat",
                        'offset': 0x112a00,
                        'entries': 0xc0 // 8,
                    },
                    {
                        'filename': "bm2dx13b.dat",
                        'offset': 0x112ac0,
                        'entries': 0x1900 // 8,
                    },
                    {
                        'filename': "bm2dx13c.dat",
                        'offset': 0x1143c0,
                        'entries': 0x4a0 // 8,
                    },
                ],
                'args': [
                    0x1353e0,
                    0x71c0 // 0x118
                ]
            },
            {
                'output': 'RomRival',
                'handler': parse_rivals,
                'archives': [
                    {
                        'filename': "RomRival.dat",
                        'offset': 0x117c70,
                        'entries': 0x19da8 // 8,
                    }
                ],
                'args': [
                    0x14c1a0,
                    0x74574 // 0x24
                ]
            },
            {
                'output': 'data1',
                'handler': parse_dats,
                'archives': [
                    {
                        'filename': "data1.dat",
                        'offset': 0x10d7f8,
                        'entries': 0X1bf0 // 16,
                    }
                ],
                'args': []
            }
        ],
    },
    {
        'title': 'beatmania IIDX 14 GOLD',
        'executable': 'SLPM_669.95',
        'data': [
            {
                'output': 'bm2dx14',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': "bm2dx14a.dat",
                        'offset': 0x11ad60,
                        'entries': 0x248 // 12,
                    },
                    {
                        'filename': "bm2dx14b.dat",
                        'offset': 0x11afa0,
                        'entries': 0x26ac // 12,
                    },
                    {
                        'filename': "bm2dx14c.dat",
                        'offset': 0x11d64c,
                        'entries': 0x72c // 12,
                    },
                ],
                'args': [
                    0x156300,
                    0x76b4 // 0x11c
                ]
            },
            {
                'output': 'romRival',
                'handler': parse_rivals,
                'archives': [
                    {
                        'filename': "romRival.dat",
                        'offset': 0x11e300,
                        'entries': 0x1bfd0 // 8,
                    }
                ],
                'args': [
                    0x15fc30,
                    0x7df28 // 0x24,
                    filetable_reader_modern
                ]
            },
            {
                'output': 'data1',
                'handler': parse_dats,
                'archives': [
                    {
                        'filename': "data1.dat",
                        'offset': 0x118500,
                        'entries': 0X1e80 // 16,
                    }
                ],
                'args': []
            }
        ],
    },
    {
        'title': 'beatmania IIDX 15 DJ TROOPERS',
        'executable': 'SLPM_551.17',
        'data': [
            {
                'output': 'bm2dx15',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': "bm2dx15a.dat",
                        'offset': 0x134020,
                        'entries': 0x240 // 12,
                    },
                    {
                        'filename': "bm2dx15b.dat",
                        'offset': 0x134260,
                        'entries': 0x27c0 // 12,
                    },
                    {
                        'filename': "bm2dx15c.dat",
                        'offset': 0x136a20,
                        'entries': 0x630 // 12,
                    },
                ],
                'args': [
                    0x16fe60,
                    0x80bc // 0x134
                ]
            },
            {
                'output': 'romRival',
                'handler': parse_rivals,
                'archives': [
                    {
                        'filename': "romRival.dat",
                        'offset': 0x1376f0,
                        'entries': 0x1bc28 // 8,
                    }
                ],
                'args': [
                    0x17a1b0,
                    0x7ceb4 // 0x24,
                    filetable_reader_modern
                ]
            },
            {
                'output': 'data1',
                'handler': parse_dats,
                'archives': [
                    {
                        'filename': "data1.dat",
                        'offset': 0x131680,
                        'entries': 0X1f80 // 16,
                    }
                ],
                'args': []
            }
        ],
    },
    {
        'title': 'beatmania IIDX 16 Empress',
        'executable': 'SLPM_552.21',
        'data': [
            {
                'output': 'BM2DX16',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': "BM2DX16A.DAT",
                        'offset': 0x13c370,
                        'entries': 0x2a0 // 12,
                    },
                    {
                        'filename': "BM2DX16B.DAT",
                        'offset': 0x13c610,
                        'entries': 0x28c8 // 12,
                    },
                    {
                        'filename': "BM2DX16C.DAT",
                        'offset': 0x13eed8,
                        'entries': 0x660 // 12,
                    },
                ],
                'args': [
                    0x178bf0,
                    0x7e54 // 0x134
                ]
            },
            {
                'output': 'ROMRIVAL',
                'handler': parse_rivals,
                'archives': [
                    {
                        'filename': "ROMRIVAL.DAT",
                        'offset': 0x13faf0,
                        'entries': 0x1c4b0 // 8,
                    }
                ],
                'args': [
                    0x182f60,
                    0x26e68 // 0x0b,
                    filetable_reader_modern
                ]
            },
            {
                'output': 'DATA1',
                'handler': parse_dats,
                'archives': [
                    {
                        'filename': "DATA1.DAT",
                        'offset': 0x139d00,
                        'entries': 0X1cf0 // 16,
                    }
                ],
                'args': []
            }
        ],
    },
    {
        'title': 'beatmania IIDX 16 Premium Best',
        'executable': 'SLPM_552.22',
        'data': [
            {
                'output': 'bm2dx16',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': "bm2dx16a.dat",
                        'offset': 0x140e90,
                        'entries': 0x2a0 // 12,
                    },
                    {
                        'filename': "bm2dx16b.dat",
                        'offset': 0x141130,
                        'entries': 0x28f8 // 12,
                    },
                    {
                        'filename': "bm2dx16c.dat",
                        'offset': 0x143a28,
                        'entries': 0x660 // 12,
                    },
                ],
                'args': [
                    0x17e0f0,
                    0x7850 // 0x134,
                ]
            },
            {
                'output': 'ROMRIVAL',
                'handler': parse_rivals,
                'archives': [
                    {
                        'filename': "ROMRIVAL.DAT",
                        'offset': 0x144640,
                        'entries': 0x1c4b0 // 8,
                    }
                ],
                'args': [
                    0x187bc0,
                    0x26e68 // 0x0b,
                    filetable_reader_modern
                ]
            },
            {
                'output': 'data1',
                'handler': parse_dats,
                'archives': [
                    {
                        'filename': "data1.dat",
                        'offset': 0x139980,
                        'entries': 0X5bd0 // 16,
                    }
                ],
                'args': []
            }
        ],
    },
    {
        'title': 'beatmania IIDX 10th Style',
        'executable': 'SLPM_661.80',
        'data': [
            {
                'output': 'data1',
                'handler': parse_dats,
                'archives': [
                    {
                        'filename': "data1.dat",
                        'offset': 0xc8e08,
                        'entries': 0x11b0 // 16,
                    }
                ],
                'args': []
            },
            {
                'output': 'DATA2',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': "DATA2.DAT",
                        'offset': 0xcdc90,
                        'entries': 0x1a38 // 8,
                    },
                ],
                'args': [
                    0x10bae0,
                    0x7d20 // 0x16c
                ]
            },
        ],
    },
    {
        'title': 'beatmania IIDX 9th Style',
        'executable': 'SLPM_659.46',
        'data': [
            {
                'output': 'DATA1',
                'handler': parse_dats,
                'archives': [
                    {
                        'filename': "DATA1.DAT",
                        'offset': 0xb7c28,
                        'entries': 0x1180 // 16,
                    }
                ],
                'args': []
            },
            {
                'output': 'DATA2',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': "DATA2.DAT",
                        'offset': 0xbd230,
                        'entries': 0x1928 // 8,
                    },
                ],
                'args': [
                    0xc1500,
                    0x7bb4 // 0x16c
                ]
            },
        ],
    },
    {
        'title': 'beatmania IIDX 8th Style',
        'executable': 'SLPM_657.68',
        'data': [
            {
                'output': 'BM2DX8A',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': os.path.join("DX2_8", "BM2DX8A.BIN"),
                        'offset': 0x19a180,
                        'entries': 0x790 // 16,
                    },
                ],
                'args': []
            },
            {
                'output': 'BM2DX8',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': os.path.join("DX2_8", "BM2DX8B.BIN"),
                        'offset': 0x19a940,
                        'entries': 0x740 // 16,
                    },
                    {
                        'filename': os.path.join("DX2_8", "BM2DX8C.BIN"),
                        'offset': 0x19b080,
                        'entries': 0x2db0 // 16,
                    }
                ],
                'args': [
                    0x1a4060,
                    0x36e0 // 0x9c
                ]
            },
        ],
    },
    {
        'title': 'beatmania IIDX 7th Style',
        'executable': 'SLPM_655.93',
        'data': [
            {
                'output': 'bm2dx7a',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': os.path.join("DX2_7", "bm2dx7a.bin"),
                        'offset': 0x1b6a50,
                        'entries': 0xa10 // 16,
                    },
                ],
                'args': []
            },
            {
                'output': 'bm2dx7',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': os.path.join("DX2_7", "bm2dx7b.bin"),
                        'offset': 0x1b7460,
                        'entries': 0x8a0 // 16,
                    },
                    {
                        'filename': os.path.join("DX2_7", "bm2dx7c.bin"),
                        'offset': 0x1b9a30,
                        'entries': 0x2bc0 // 16,
                    }
                ],
                'args': [
                    0x1c1af0,
                    0x3840 // 0xa0,
                ]
            },
        ],
    },
    {
        'title': 'beatmania IIDX 6th Style',
        'executable': 'SLPM_651.56',
        'data': [
            {
                'output': 'BM2DX6',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': os.path.join("DX2_6", "BM2DX6A.bin"),
                        'offset':  0x180058,
                        'entries': 0x1590 // 16,
                    },
                    {
                        'filename': os.path.join("DX2_6", "BM2DX6B.bin"),
                        'offset': 0x1815e8,
                        'entries': 0x5b0 // 16,
                    },
                ],
                'args': [
                    0x1885b8,
                    0x8660 // 0xa0
                ]
            },
        ],
    },
    {
        'title': 'beatmania IIDX 5th Style',
        'executable': 'SLPM_650.49',
        'data': [
            {
                'output': 'bm2dx5',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': os.path.join("DX2_5", "bm2dx5.bin"),
                        'offset':  0x1837d8,
                        'entries': 0x1230 // 16,
                    },
                ],
                'args': [
                    0xae520,
                    0x5af6 // 0xa4
                ]
            },
        ],
    },
    {
        'title': 'beatmania IIDX 4th Style',
        'executable': 'SLPM_650.26',
        'data': [
            {
                'output': 'bm2dx4',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': os.path.join("DX2_4", "BM2DX4.bin"),
                        'offset':  0x137450,
                        'entries': 0x9d8 // 12,
                    },
                ],
                'args': [
                    0x8bc98,
                    0x2010 // 0x90
                ]
            },
        ],
    },
]

FILETABLE_READERS = {
    'slpm_650.06': filetable_reader_3rd,
    'slpm_655.93': filetable_reader_8th,
    'slpm_657.68': filetable_reader_8th,
    'slpm_651.56': filetable_reader_8th,
    'slpm_650.49': filetable_reader_8th,
    'slpm_650.26': filetable_reader_3rd,
    'slpm_664.26': filetable_reader_modern,
    'slpm_666.21': filetable_reader_modern,
    'slpm_668.28': filetable_reader_modern,
    'slpm_669.95': filetable_reader_modern2,
    'slpm_551.17': filetable_reader_modern2,
    'slpm_552.21': filetable_reader_modern2,
    'slpm_552.22': filetable_reader_modern2,
    'slpm_661.80': filetable_reader_modern,
    'slpm_659.46': filetable_reader_modern,
    'slus_212.39': filetable_reader_modern,
}

SONGLIST_READERS = {
    'slpm_650.06': songlist_reader_3rd,
    'slpm_650.26': songlist_reader_4th,
    'slpm_650.49': songlist_reader_5th,
    'slpm_651.56': songlist_reader_6th,
    'slpm_655.93': songlist_reader_7th,
    'slpm_657.68': songlist_reader_8th,
    'slpm_659.46': songlist_reader_9th,
    'slpm_661.80': songlist_reader_9th,
    'slpm_664.26': songlist_reader_red,
    'slpm_666.21': songlist_reader_happysky,
    'slpm_668.28': songlist_reader_distorted,
    'slpm_669.95': songlist_reader_gold,
    'slpm_551.17': songlist_reader_djtroopers,
    'slpm_552.21': songlist_reader_empress,
    'slpm_552.22': songlist_reader_empress,
    'slus_212.39': songlist_reader_beatmaniaus,
}

RIVALS_READERS = {
    'slpm_666.21': rivals_reader_happy_sky,
    'slpm_668.28': rivals_reader_distorted,
    'slpm_669.95': rivals_reader_distorted,
    'slpm_551.17': rivals_reader_distorted,
    'slpm_552.21': rivals_reader_empress,
    'slpm_552.22': rivals_reader_empress,
}

DAT_FILETABLE_READERS = {
    'slpm_664.26': dat_filetable_reader_modern,
    'slpm_666.21': dat_filetable_reader_modern,
    'slpm_668.28': dat_filetable_reader_modern,
    'slpm_669.95': dat_filetable_reader_modern,
    'slpm_551.17': dat_filetable_reader_modern,
    'slpm_552.21': dat_filetable_reader_modern,
    'slpm_552.22': dat_filetable_reader_modern,
    'slpm_661.80': dat_filetable_reader_modern,
    'slpm_659.46': dat_filetable_reader_modern,
    'slus_212.39': dat_filetable_reader_modern,
}

ENCRYPTION_KEYS = {
    'slpm_669.95': generate_encryption_key_gold(),
    'slpm_551.17': generate_encryption_key_djtroopers(),
    'slpm_552.21': generate_encryption_key_empress(),
    'slpm_552.22': generate_encryption_key_empress(),
}


for game in game_data:
    if not os.path.exists(game['executable']):
        continue

    print("Extracting data from", game['title'])

    for data in game['data']:
        data['handler'](game['executable'], data['archives'], data['output'], *data['args'])
