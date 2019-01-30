import struct

CHUNK_SIZE = 0x800


def dat_filetable_reader_modern(executable_filename, filename, offset, file_count, base_file_id=0):
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
                'file_id': base_file_id + i,
            })

    return file_entries


def filetable_reader_old(executable_filename, filename, offset, file_count, base_file_id=0):
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
                'file_id': base_file_id + i,
            })

    return file_entries


def filetable_reader_old2(executable_filename, filename, offset, file_count, base_file_id=0):
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
                'file_id': base_file_id + i,
            })

    return file_entries


def filetable_reader_modern(executable_filename, filename, offset, file_count, base_file_id=0):
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
                'file_id': base_file_id + i,
            })

    return file_entries


def filetable_reader_modern2(executable_filename, filename, offset, file_count, base_file_id=0):
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
                'file_id': base_file_id + i,
            })

    return file_entries
