import json
import os
import struct

import common
import filetable_readers


class Iidx8thCsHandler:
    @staticmethod
    def is_match(filename):
        return filename == "SLPM_657.68"


    @staticmethod
    def read_songlist(executable_filename, songlist_offset, songlist_count, file_entries):
        with open(executable_filename, "rb") as infile:
            infile.seek(songlist_offset)

            for i in range(songlist_count):
                infile.seek(songlist_offset + i * 0x9c, 0)

                internal_title_offset, title_offset = struct.unpack("<II", infile.read(8))

                internal_title = common.read_string(infile, internal_title_offset - 0xfff80)
                title = common.read_string(infile, title_offset - 0xfff80)

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
                    file_entries[file_index]['real_filename'].append("%s [%s].ply" % (title, common.OLD_DIFFICULTY_MAPPING.get(index, str(index))))
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

                        if file_index >= 116:
                            file_index += 116

                        if is_keysound:
                            file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, pair_index))
                        else:
                            file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, pair_index))

        return file_entries


    @staticmethod
    def extract(exe_filename, input_folder, output_folder):
        main_archive_file_entries = []
        main_archive_file_entries += filetable_readers.filetable_reader_old2(exe_filename, os.path.join(input_folder, "DX2_8", "BM2DX8A.BIN"), 0x19a180, 0x790 // 8, len(main_archive_file_entries))
        main_archive_file_entries += filetable_readers.filetable_reader_old2(exe_filename, os.path.join(input_folder, "DX2_8", "BM2DX8B.BIN"), 0x19a940, 0x740 // 8, len(main_archive_file_entries))
        main_archive_file_entries += filetable_readers.filetable_reader_old2(exe_filename, os.path.join(input_folder, "DX2_8", "BM2DX8C.BIN"), 0x19b080, 0x2db0 // 8, len(main_archive_file_entries))

        Iidx8thCsHandler.read_songlist(exe_filename, 0x1a4060, 0x36e0 // 0x9c, main_archive_file_entries)

        common.extract_files(main_archive_file_entries, output_folder)

        common.extract_overlays(main_archive_file_entries, output_folder, { # 8th
            'base_offset': 0xfff80,
            'palette_table': 0x124a20,
            'animation_table': 0x124ba0,
            'animation_data_table': 0x127480,
            'tile_table': 0x136f10,
            'animation_parts_table': 0x191bd0,
        })


def get_class():
    return Iidx8thCsHandler
