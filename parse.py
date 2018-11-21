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


def parse_file(executable_filename, filename, offset, file_count, output_folder, extract=True):
    filetable_readers = {
        'slpm_650.06': filetable_reader_3rd,
        'slpm_666.21': filetable_reader_modern,
        'slus_212.39': filetable_reader_modern,
    }

    filetable_reader = filetable_readers[executable_filename.lower()] if executable_filename.lower() in filetable_readers else None

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

        # TODO: Figure out proper offsets for data
        for i in range(songlist_count):
            infile.seek(songlist_offset + i * 0x144, 0)

            title = infile.read(0x40).decode('shift-jis').strip('\0')

            if len(title) == 0:
                break

            infile.seek(0x14, 1)
            video_idx = struct.unpack("<I", infile.read(4))[0]

            infile.seek(0x94, 1)
            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            file_entries[video_idx]['real_filename'].append("%s.mpg" % title)

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].1" % (title, DIFFICULTY_MAPPING.get(index, str(index))))

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
                break

            infile.seek(0x1c, 1)
            video_idx = struct.unpack("<I", infile.read(4))[0]

            infile.seek(0xd0, 1)

            print("offset: %08x" % infile.tell())
            charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
            sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

            file_entries[video_idx]['real_filename'].append("%s.mpg" % title)

            for index, file_index in enumerate(charts_idx):
                if file_index == 0xffffffff or file_index == 0x00:
                    # Invalid
                    continue

                file_entries[file_index]['real_filename'].append("%s [%s].1" % (title, DIFFICULTY_MAPPING.get(index, str(index))))

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

    songlist_readers = {
        'slpm_666.21': songlist_reader_happysky,
        'slus_212.39': songlist_reader_beatmaniaus,
    }

    songlist_reader = songlist_readers[executable_filename.lower()] if executable_filename.lower() in songlist_readers else None

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


def parse_rivals(executable_filename, archives, output_folder, rivals_offset, rivals_count):
    rivals_readers = {
        'slpm_666.21': rivals_reader_happy_sky,
    }

    file_entries = []
    for archive in archives:
        file_entries += parse_file(executable_filename, archive['filename'], archive['offset'], archive['entries'], output_folder, extract=False)

    rivals_reader = rivals_readers[executable_filename.lower()] if executable_filename.lower() in rivals_readers else None

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
    dat_filetable_readers = {
        'slus_212.39': dat_filetable_reader_modern,
        'slpm_666.21': dat_filetable_reader_modern,
    }

    dat_filetable_reader = dat_filetable_readers[executable_filename.lower()] if executable_filename.lower() in dat_filetable_readers else None

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
]

for game in game_data:
    if not os.path.exists(game['executable']):
        continue

    print("Extracting data from", game['title'])

    for data in game['data']:
        data['handler'](game['executable'], data['archives'], data['output'], *data['args'])
