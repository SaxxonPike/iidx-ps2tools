import json
import os
import struct

import common
import filetable_readers


class Iidx5thCsHandler:
    @staticmethod
    def is_match(filename):
        return filename == "SLPM_650.49"


    @staticmethod
    def read_songlist(executable_filename, songlist_offset, songlist_count, file_entries):
        with open(executable_filename, "rb") as infile:
            chart_data_buffer = infile.read()

            infile.seek(songlist_offset)

            for i in range(songlist_count):
                infile.seek(songlist_offset + i * 0xa4, 0)

                internal_title_offset, title_offset = struct.unpack("<II", infile.read(8))

                internal_title = common.read_string(infile, internal_title_offset - 0xff000)
                title = common.read_string(infile, title_offset - 0xff000)

                if len(title) == 0:
                    title = "%d" % i

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
                    file_entries[video_idx]['song_id'] = i

                    file_entries[video_idx+1]['real_filename'].append("%s [1].mpg" % title)
                    file_entries[video_idx+1]['song_id'] = i

                if overlay_idx not in [0xffff, 0x00]:
                    overlay_filename = "%s.if" % title
                    file_entries[overlay_idx]['real_filename'].append(overlay_filename)
                    file_entries[overlay_idx]['overlays'] = {
                        'exe': executable_filename,
                        'palette': overlay_palette,
                        'indexes': overlay_idxs
                    }
                    file_entries[overlay_idx]['song_id'] = i

                for index, file_index in enumerate(charts_idx):
                    if file_index == 0xffffffff or file_index == 0x00:
                        # Invalid
                        continue

                    file_entries.append({
                        'filename': executable_filename,
                        'offset': file_index-0xff000,
                        'size': len(chart_data_buffer) - file_index-0xff000,
                        'compression': common.decode_lz,
                        'real_filename': [
                            "%s [%s].ply" % (title, common.OLD_DIFFICULTY_MAPPING.get(index, str(index)))
                        ],
                        'file_id': len(file_entries),
                        'song_id': i,
                    })

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

        return file_entries


    @staticmethod
    def extract(exe_filename, input_folder, output_folder, raw_mode, conversion_mode):
        main_archive_file_entries = []
        main_archive_file_entries += filetable_readers.filetable_reader_old2(exe_filename, os.path.join(input_folder, "DX2_5", "BM2DX5.BIN"), 0x1837d8, 0x1230 // 16, len(main_archive_file_entries))

        Iidx5thCsHandler.read_songlist(exe_filename, 0xae520, 0x5af6 // 0xa4, main_archive_file_entries)

        common.extract_files(main_archive_file_entries, output_folder, raw_mode)

        common.extract_overlays(main_archive_file_entries, output_folder, { # 5th
            'base_offset': 0xff000,
            'palette_table': 0x174828,
            'animation_table': 0xb44a8,
            'animation_data_table': 0xb9608,
            'tile_table': 0xd2c70,
            'animation_parts_table': 0x163190,
        })


def get_class():
    return Iidx5thCsHandler
