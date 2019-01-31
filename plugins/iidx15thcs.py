import json
import os
import struct

import common
import filetable_readers


class Iidx15thCsHandler:
    @staticmethod
    def is_match(filename):
        return filename == "SLPM_551.17"


    @staticmethod
    def generate_encryption_key():
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


    @staticmethod
    def read_songlist(executable_filename, songlist_offset, songlist_count, file_entries, animation_file_entries):
        with open(executable_filename, "rb") as infile:
            infile.seek(songlist_offset)

            for i in range(songlist_count):
                infile.seek(songlist_offset + i * 0x134, 0)

                title = infile.read(0x40).decode('shift-jis').strip('\0')

                if len(title) == 0:
                    title = "%d" % i

                infile.seek(0x18, 1)
                videos_idx = struct.unpack("<II", infile.read(8))

                infile.seek(0x34, 1)

                main_overlay_file_idx = struct.unpack("<I", infile.read(4))[0]

                overlays = []
                for oidx in range(0, 5):
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
                    file_entries[file_index]['encryption'] = Iidx15thCsHandler.generate_encryption_key()
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
        main_archive_file_entries += filetable_readers.filetable_reader_modern2(exe_filename, os.path.join(input_folder, "bm2dx15a.dat"), 0x134020, 0x240 // 12, len(main_archive_file_entries))
        main_archive_file_entries += filetable_readers.filetable_reader_modern2(exe_filename, os.path.join(input_folder, "bm2dx15b.dat"), 0x134260, 0x27c0 // 12, len(main_archive_file_entries))
        main_archive_file_entries += filetable_readers.filetable_reader_modern2(exe_filename, os.path.join(input_folder, "bm2dx15c.dat"), 0x136a20, 0x630 // 12, len(main_archive_file_entries))

        animation_file_entries = filetable_readers.dat_filetable_reader_modern(exe_filename, os.path.join(input_folder, "data1.dat"), 0x131680, 0X1f80 // 16)

        Iidx15thCsHandler.read_songlist(exe_filename, 0x16fe60, 0x80bc // 0x134, main_archive_file_entries, animation_file_entries)

        common.extract_files(main_archive_file_entries, output_folder)
        common.extract_files(animation_file_entries, output_folder)
        common.extract_overlays(animation_file_entries, output_folder, None)


def get_class():
    return Iidx15thCsHandler
