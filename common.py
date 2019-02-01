import os

import blowfish

import ps2overlay

from animtool.animation_ps2 import AnimationPs2

DIFFICULTY_MAPPING = {
    0: 'SP NORMAL',
    1: 'DP NORMAL',
    2: 'SP HYPER',
    3: 'DP HYPER',
    4: 'SP ANOTHER',
    5: 'DP ANOTHER',
    6: 'SP BEGINNER',
    7: 'DP BLACK',
    8: 'DP BLACK',
}

OLD_DIFFICULTY_MAPPING = {
    0: 'SP HYPER',
    1: 'DP HYPER',
    2: 'SP ANOTHER',
    3: 'DP ANOTHER',
    4: 'SP NORMAL',
    5: 'DP NORMAL',
    6: 'SP BEGINNER',
    7: 'SP BLACK',
    8: 'DP BLACK',
}

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


def extract_file(filename, entry, output_filename):
    if os.path.exists(output_filename):
        base_filename, ext = os.path.splitext(output_filename)
        output_filename = "%s [%04x]%s" % (base_filename, entry['file_id'], ext)

    print("Extracting", output_filename)

    with open(filename, "rb") as infile:
        infile.seek(entry['offset'])
        data = infile.read(entry['size'])

        if entry.get('encryption', None) is not None:
            data = decrypt_blowfish(data, entry['encryption'])

        if entry.get('compression', None) is not None:
            data = entry['compression'](data)

        with open(output_filename, "wb") as outfile:
            outfile.write(data)


def extract_files(file_entries, output_folder, raw_mode, base_file_id=0):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for entry in file_entries[::]:
        if raw_mode:
            entry['real_filename'] = []

        if not entry['real_filename']:
            entry['real_filename'].append("file_%04d.bin" % (entry['file_id'] + base_file_id))

        for filename in entry['real_filename']:
            if 'title' in entry and not raw_mode:
                output_song_folder = os.path.join(output_folder, "%s [%04d]" % (entry['title'], entry['song_id']))

                if not os.path.exists(output_song_folder):
                    os.makedirs(output_song_folder)

            else:
                output_song_folder = output_folder

            output_filename = os.path.join(output_song_folder, get_sanitized_filename(filename))
            extract_file(entry['filename'], entry, output_filename)


def extract_overlays(file_entries, output_folder, overlay_exe_offsets):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for entry in file_entries[::]:
        if not entry['real_filename']:
            entry['real_filename'].append("file_%04d.bin" % entry['file_id'])

        for filename in entry['real_filename']:
            input_filename = os.path.join(output_folder, get_sanitized_filename(filename))

            if not os.path.exists(input_filename):
                continue

            if entry.get('overlays', None) is not None:
                for overlay_idx in entry['overlays']['indexes']:
                    ifs_filename = os.path.join(output_folder, get_sanitized_filename(filename))
                    output_filename = os.path.join(output_folder, get_sanitized_filename("%s [%04x]" % (ifs_filename.replace(".if", ""), overlay_idx)))
                    ps2overlay.extract_overlay(entry['overlays']['exe'], ifs_filename, entry['overlays']['palette'], overlay_idx, output_filename, overlay_exe_offsets)

            if entry.get('overlays_new', None) is not None:
                animation_id = []

                for overlay in entry['overlays_new']:
                    animation_id.append(overlay['animation_id'])

                ifs_filename = os.path.join(output_folder, get_sanitized_filename(filename))
                output_filename = os.path.join(output_folder, get_sanitized_filename("%s [%04x]" % (filename.replace(".if", ""), overlay['overlay_idx'])))

                animparser = AnimationPs2(ifs_filename, 8, False)
                animparser.render(animation_id, output_filename, False)
