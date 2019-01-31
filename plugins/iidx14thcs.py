import json
import os
import struct

import common
import filetable_readers


class Iidx14thCsHandler:
    @staticmethod
    def is_match(filename):
        return filename == "SLPM_669.95"


    @staticmethod
    def generate_encryption_key():
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


    @staticmethod
    def read_songlist(executable_filename, songlist_offset, songlist_count, file_entries, animation_file_entries):
        with open(executable_filename, "rb") as infile:
            infile.seek(songlist_offset)

            for i in range(songlist_count):
                infile.seek(songlist_offset + i * 0x11c, 0)

                title = infile.read(0x40).decode('shift-jis').strip('\0')

                if len(title) == 0:
                    title = "%d" % i

                infile.seek(0x14, 1)
                videos_idx = struct.unpack("<II", infile.read(8))

                infile.seek(0x28, 1)

                main_overlay_file_idx = struct.unpack("<I", infile.read(4))[0]

                overlays = []
                for oidx in range(0, 6):
                    animation_idx, overlay_idx = struct.unpack("<HH", infile.read(4))

                    if overlay_idx != 0:
                        overlays.append({
                            'animation_id': animation_idx,
                            'overlay_idx': overlay_idx,
                            'index': oidx,
                        })

                if main_overlay_file_idx != 0:
                    if 'overlays_new' not in animation_file_entries[main_overlay_file_idx]:
                        animation_file_entries[main_overlay_file_idx]['overlays_new'] = overlays

                    animation_file_entries[main_overlay_file_idx]['real_filename'].append("%s.if" % (title))

                infile.seek(0x14, 1)
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

                    file_entries[file_index]['real_filename'].append("%s [%s].ply" % (title, common.DIFFICULTY_MAPPING.get(index, str(index))))
                    file_entries[file_index]['encryption'] = Iidx14thCsHandler.generate_encryption_key()
                    file_entries[file_index]['compression'] = common.decode_lz

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


    @staticmethod
    def extract(exe_filename, input_folder, output_folder):
        main_archive_file_entries = []
        main_archive_file_entries += filetable_readers.filetable_reader_modern2(exe_filename, os.path.join(input_folder, "bm2dx14a.dat"), 0x11ad60, 0x248 // 12, len(main_archive_file_entries))
        main_archive_file_entries += filetable_readers.filetable_reader_modern2(exe_filename, os.path.join(input_folder, "bm2dx14b.dat"), 0x11afa0, 0x26ac // 12, len(main_archive_file_entries))
        main_archive_file_entries += filetable_readers.filetable_reader_modern2(exe_filename, os.path.join(input_folder, "bm2dx14c.dat"), 0x11d64c, 0x72c // 12, len(main_archive_file_entries))

        animation_file_entries = filetable_readers.dat_filetable_reader_modern(exe_filename, os.path.join(input_folder, "data1.dat"), 0x118500, 0X1e80 // 16)

        Iidx14thCsHandler.read_songlist(exe_filename, 0x156300, 0x76b4 // 0x11c, main_archive_file_entries, animation_file_entries)

        common.extract_files(main_archive_file_entries, output_folder)
        common.extract_files(animation_file_entries, output_folder, len(main_archive_file_entries))
        common.extract_overlays(animation_file_entries, output_folder, None)


def get_class():
    return Iidx14thCsHandler
