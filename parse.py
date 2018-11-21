import os
import struct

CHUNK_SIZE = 0x800

DIFFICULTY_MAPPING = {
    0: 'SP NORMAL',
    1: 'SP HYPER',
    2: 'SP ANOTHER',
    3: 'DP NORMAL',
    4: 'DP HYPER',
    5: 'DP ANOTHER',
    6: 'SP BEGINNER',
    7: 'DP BEGINNER', # Never used?
}

def decode_lz(input_data):
    # Based on https://github.com/SaxxonPike/scharfrichter/blob/master/Scharfrichter/Compression/BemaniLZ.cs
    BUFFER_MASK = 0x3ff

    control = 0

    input_data = bytearray(input_data)
    idx = 0

    buffer = bytearray([0] * 0x400)
    buffer_idx = 0

    output = bytearray([])

    while True:
        loop = False

        control >>= 1
        if control < 0x100:
            control = input_data[idx] | 0xff00
            idx += 1

        data = input_data[idx]
        idx += 1

        if (control & 1) == 0:
            output.append(data)
            buffer[buffer_idx] = data
            buffer_idx = (buffer_idx + 1) & BUFFER_MASK
            continue

        if (data & 0x80) == 0:
            distance = input_data[idx] | ((data & 0x03) << 8)
            idx += 1
            length = (data >> 2) + 2
            loop = True

        elif (data & 0x40) == 0:
            distance = (data & 0x0f) + 1
            length = (data >> 4) - 7
            loop = True

        if loop:
            while length >= 0:
                length -= 1

                data = buffer[(buffer_idx - distance) & BUFFER_MASK]
                output.append(data)
                buffer[buffer_idx] = data
                buffer_idx = (buffer_idx + 1) & BUFFER_MASK

            continue

        if data == 0xff:
            break

        length = data - 0xb9
        while length >= 0:
            data = input_data[idx]
            idx += 1
            output.append(data)
            buffer[buffer_idx] = data
            buffer_idx = (buffer_idx + 1) & BUFFER_MASK
            length -= 1

    return output


def get_sanitized_filename(filename, invalid_chars='<>:;\"\\/|?*'):
    for c in invalid_chars:
        filename = filename.replace(c, "_")

    return filename


# Generic extraction code
def extract_file(filename, table, index, output_folder, output_filename):
    if index == 0:
        return

    entry = table[index] if index < len(table) else None

    if entry is None:
        return

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    with open(filename, "rb") as infile:
        print("Extracting", output_filename)

        infile.seek(entry['offset'])
        data = infile.read(entry['size'])

        if entry.get('compression', None) is not None:
            data = entry['compression'](data)

        open(os.path.join(output_folder, get_sanitized_filename(output_filename)), "wb").write(data)


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

        for i in range(file_count):
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
def songlist_reader_happysky(executable_filename, file_entries, songlist_offset, songlist_count):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x144, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x14, 1)
            video_idx, video_idx2 = struct.unpack("<II", infile.read(8))

            infile.seek(0x90, 1)
            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            if video_idx != 0xffffffff and video_idx != 0:
                file_entries[video_idx]['real_filename'].append("%s.mpg" % title)

            if video_idx2 != 0xffffffff and video_idx2 != 0:
                file_entries[video_idx2]['real_filename'].append("%s.mpg" % title)

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].1" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['compression'] = decode_lz

            is_keysound = False
            for index, file_index in enumerate(sounds_idx):
                if (index % 2) == 0:
                    is_keysound = not is_keysound

                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                if is_keysound:
                    file_entries[file_index]['real_filename'].append("%s [%d].ksnd" % (title, index % 2))
                else:
                    file_entries[file_index]['real_filename'].append("%s [%d].bsnd" % (title, index % 2))

    return file_entries

def songlist_reader_10(executable_filename, file_entries, songlist_offset, songlist_count):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x16c, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x18, 1)
            video_idx, video_idx2 = struct.unpack("<II", infile.read(8))

            infile.seek(0xcc, 1)
            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            if video_idx != 0xffffffff and video_idx != 0:
                file_entries[video_idx]['real_filename'].append("%s [0].mpg" % title)

            if video_idx2 != 0xffffffff and video_idx2 != 0:
                file_entries[video_idx2]['real_filename'].append("%s [1].mpg" % title)

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].1" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['compression'] = decode_lz

            is_keysound = False
            for index, file_index in enumerate(sounds_idx):
                if (index % 2) == 0:
                    is_keysound = not is_keysound

                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                if is_keysound:
                    file_entries[file_index]['real_filename'].append("%s [%d].ksnd" % (title, index % 2))
                else:
                    file_entries[file_index]['real_filename'].append("%s [%d].bsnd" % (title, index % 2))

    return file_entries


def songlist_reader_red(executable_filename, file_entries, songlist_offset, songlist_count):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x140, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x1c, 1)
            video_idx, video_idx2 = struct.unpack("<II", infile.read(8))

            infile.seek(0x9c, 1)
            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            if video_idx != 0xffffffff and video_idx != 0:
                file_entries[video_idx]['real_filename'].append("%s [0].mpg" % title)

            if video_idx2 != 0xffffffff and video_idx2 != 0:
                file_entries[video_idx2]['real_filename'].append("%s [1].mpg" % title)

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].1" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['compression'] = decode_lz

            is_keysound = False
            for index, file_index in enumerate(sounds_idx):
                if (index % 2) == 0:
                    is_keysound = not is_keysound

                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                if is_keysound:
                    file_entries[file_index]['real_filename'].append("%s [%d].ksnd" % (title, index % 2))
                else:
                    file_entries[file_index]['real_filename'].append("%s [%d].bsnd" % (title, index % 2))

    return file_entries


def songlist_reader_distorted(executable_filename, file_entries, songlist_offset, songlist_count):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x118, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x14, 1)
            video_idx, video_idx2 = struct.unpack("<II", infile.read(8))

            infile.seek(0x5c, 1)
            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            if video_idx != 0xffffffff and video_idx != 0:
                file_entries[video_idx]['real_filename'].append("%s [0].mpg" % title)

            if video_idx2 != 0xffffffff and video_idx2 != 0:
                file_entries[video_idx2]['real_filename'].append("%s [1].mpg" % title)

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].1" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['compression'] = decode_lz

            is_keysound = False
            for index, file_index in enumerate(sounds_idx):
                if (index % 2) == 0:
                    is_keysound = not is_keysound

                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                if is_keysound:
                    file_entries[file_index]['real_filename'].append("%s [%d].ksnd" % (title, index % 2))
                else:
                    file_entries[file_index]['real_filename'].append("%s [%d].bsnd" % (title, index % 2))

    return file_entries

def songlist_reader_gold(executable_filename, file_entries, songlist_offset, songlist_count):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x11c, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x14, 1)
            video_idx, video_idx2 = struct.unpack("<II", infile.read(8))

            infile.seek(0x58, 1)
            charts_idx = struct.unpack("<IIIIIIIIII", infile.read(0x28)) # 28??
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            if video_idx != 0xffffffff and video_idx != 0:
                file_entries[video_idx]['real_filename'].append("%s [0].mpg" % title)

            if video_idx2 != 0xffffffff and video_idx2 != 0:
                file_entries[video_idx2]['real_filename'].append("%s [1].mpg" % title)

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].1" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                #file_entries[file_index]['compression'] = decode_lz # Not LZ anymore

            is_keysound = False
            for index, file_index in enumerate(sounds_idx):
                if (index % 2) == 0:
                    is_keysound = not is_keysound

                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                if is_keysound:
                    file_entries[file_index]['real_filename'].append("%s [%d].ksnd" % (title, index % 2))
                else:
                    file_entries[file_index]['real_filename'].append("%s [%d].bsnd" % (title, index % 2))

    return file_entries

def songlist_reader_djtroopers(executable_filename, file_entries, songlist_offset, songlist_count):
    with open(executable_filename, "rb") as infile:
        infile.seek(songlist_offset)

        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x134, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                title = "%d" % i

            infile.seek(0x18, 1)
            video_idx, video_idx2 = struct.unpack("<II", infile.read(8))

            infile.seek(0x60, 1)
            charts_idx = struct.unpack("<IIIIIIIIII", infile.read(0x28)) # 28??
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            if video_idx != 0xffffffff and video_idx != 0:
                file_entries[video_idx]['real_filename'].append("%s [0].mpg" % title)

            if video_idx2 != 0xffffffff and video_idx2 != 0:
                file_entries[video_idx2]['real_filename'].append("%s [1].mpg" % title)

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].1" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                #file_entries[file_index]['compression'] = decode_lz # Not LZ anymore

            is_keysound = False
            for index, file_index in enumerate(sounds_idx):
                if (index % 2) == 0:
                    is_keysound = not is_keysound

                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                if is_keysound:
                    file_entries[file_index]['real_filename'].append("%s [%d].ksnd" % (title, index % 2))
                else:
                    file_entries[file_index]['real_filename'].append("%s [%d].bsnd" % (title, index % 2))

    return file_entries


def songlist_reader_beatmaniaus(executable_filename, file_entries, songlist_offset, songlist_count):
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

                file_entries[file_index]['real_filename'].append("%s [%s].1" % (title, DIFFICULTY_MAPPING.get(index, str(index))))
                file_entries[file_index]['compressed'] = True

            is_keysound = False
            for index, file_index in enumerate(sounds_idx):
                if (index % 2) == 0:
                    is_keysound = not is_keysound

                if file_index == 0xffff or file_index == 0x00:
                    # Invalid
                    continue

                if is_keysound:
                    file_entries[file_index]['real_filename'].append("%s [%d].ksnd" % (title, index % 2))
                else:
                    file_entries[file_index]['real_filename'].append("%s [%d].bsnd" % (title, index % 2))

    return file_entries


def parse_songlist(executable_filename, file_entries, songlist_offset, songlist_count):
    if songlist_offset is None or songlist_count is None:
        return file_entries

    songlist_reader = SONGLIST_READERS[executable_filename.lower()] if executable_filename.lower() in SONGLIST_READERS else None

    if songlist_reader is not None:
        return songlist_reader(executable_filename, file_entries, songlist_offset, songlist_count)

    return file_entries


def parse_archives(executable_filename, archives, output_folder, songlist_offset=None, songlist_count=None):
    file_entries = []

    for archive in archives:
        file_entries += parse_file(executable_filename, archive['filename'], archive['offset'], archive['entries'], output_folder, extract=False)

    file_entries = parse_songlist(executable_filename, file_entries, songlist_offset, songlist_count)

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
                'args': []
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
                    0x7850 // 0x134
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
                'output': 'BM2DX8',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': os.path.join("DX2_8", "BM2DX8A.BIN"),
                        'offset': 0x19a180,
                        'entries': 0x790 // 16,
                    },
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
                'args': []
            },
        ],
    },
    {
        'title': 'beatmania IIDX 7th Style',
        'executable': 'SLPM_655.93',
        'data': [
            {
                'output': 'bm2dx7',
                'handler': parse_archives,
                'archives': [
                    {
                        'filename': os.path.join("DX2_7", "bm2dx7a.bin"),
                        'offset': 0x1b6a50,
                        'entries': 0xa10 // 16,
                    },
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
                'args': []
            },
        ],
    },
]

FILETABLE_READERS = {
    'slpm_650.06': filetable_reader_3rd,
    'slpm_655.93': filetable_reader_8th,
    'slpm_657.68': filetable_reader_8th,
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
    #'slpm_650.06': songlist_reader_3rd,
    #'slpm_657.68': songlist_reader_8th,
    #'slpm_655.93': songlist_reader_7th,
    'slpm_664.26': songlist_reader_red,
    'slpm_666.21': songlist_reader_happysky,
    'slpm_668.28': songlist_reader_distorted,
    'slpm_669.95': songlist_reader_gold,
    'slpm_551.17': songlist_reader_djtroopers,
    'slpm_552.21': songlist_reader_djtroopers,
    'slpm_552.22': songlist_reader_djtroopers,
    'slpm_661.80': songlist_reader_10,
    'slpm_659.46': songlist_reader_10,
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


for game in game_data:
    if not os.path.exists(game['executable']):
        continue

    print("Extracting data from", game['title'])

    for data in game['data']:
        data['handler'](game['executable'], data['archives'], data['output'], *data['args'])
