import json
import os
import struct

import common
import filetable_readers


class Iidx13thCsHandler:
    @staticmethod
    def is_match(filename):
        return filename == "SLPM_668.28"

    @staticmethod
    def read_songlist(executable_filename, songlist_offset, songlist_count, file_entries, animation_file_entries):
        with open(executable_filename, "rb") as infile:
            infile.seek(songlist_offset)

            for i in range(songlist_count):
                infile.seek(songlist_offset + i * 0x118, 0)

                title = infile.read(0x40).decode('shift-jis').strip('\0').strip()

                if len(title) == 0:
                    title = "%d" % i

                infile.seek(0x0c, 1)

                diff_sp_normal, diff_sp_hyper, diff_sp_another = struct.unpack("<BBB", infile.read(3))
                diff_dp_normal, diff_dp_hyper, diff_dp_another = struct.unpack("<BBB", infile.read(3))

                infile.seek(0x02, 1)

                videos_idx = struct.unpack("<II", infile.read(8))

                infile.seek(0x04, 1)

                main_overlay_file_idx = struct.unpack("<I", infile.read(4))[0]

                overlays = []
                for oidx in range(0, 8):
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
                    animation_file_entries[main_overlay_file_idx]['song_id'] = i

                infile.seek(0x34, 1)
                charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
                sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))

                for index, file_index in enumerate(videos_idx):
                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    file_entries[file_index]['real_filename'].append("%s [%d].mpg" % (title, index))
                    file_entries[file_index]['song_id'] = i

                for index, file_index in enumerate(charts_idx):
                    if file_index == 0xffffffff or file_index == 0x00:
                        # Invalid
                        continue

                    file_entries[file_index]['real_filename'].append("%s [%s].ply" % (title, common.DIFFICULTY_MAPPING.get(index, str(index))))
                    file_entries[file_index]['compression'] = common.decode_lz
                    file_entries[file_index]['song_id'] = i

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

                        file_entries[file_index]['song_id'] = i



    @staticmethod
    def extract(exe_filename, input_folder, output_folder, raw_mode, conversion_mode):
        main_archive_file_entries = []
        main_archive_file_entries += filetable_readers.filetable_reader_modern(exe_filename, os.path.join(input_folder, "bm2dx13a.dat"), 0x112a00, 0xc0 // 8, len(main_archive_file_entries))
        main_archive_file_entries += filetable_readers.filetable_reader_modern(exe_filename, os.path.join(input_folder, "bm2dx13b.dat"), 0x112ac0, 0x1900 // 8, len(main_archive_file_entries))
        main_archive_file_entries += filetable_readers.filetable_reader_modern(exe_filename, os.path.join(input_folder, "bm2dx13c.dat"), 0x1143c0, 0x4a0 // 8, len(main_archive_file_entries))

        animation_file_entries = filetable_readers.dat_filetable_reader_modern(exe_filename, os.path.join(input_folder, "data1.dat"), 0x10d7f8, 0X1bf0 // 16)

        Iidx13thCsHandler.read_songlist(exe_filename, 0x1353e0, 0x71c0 // 0x118, main_archive_file_entries, animation_file_entries)

        common.extract_files(main_archive_file_entries, output_folder, raw_mode)
        common.extract_files(animation_file_entries, output_folder, raw_mode, conversion_mode, len(main_archive_file_entries))
        common.extract_overlays(animation_file_entries, output_folder, None)


def get_class():
    return Iidx13thCsHandler
