import json
import os
import struct

import common
import filetable_readers


class Iidx7thCsHandler:
    @staticmethod
    def is_match(filename):
        return filename == "SLPM_655.93"


    @staticmethod
    def read_songlist(executable_filename, songlist_offset, songlist_count, file_entries):
        song_metadata = {}

        with open(executable_filename, "rb") as infile:
            infile.seek(songlist_offset)

            for i in range(songlist_count):
                infile.seek(songlist_offset + i * 0xa0, 0)

                internal_title_offset, title_offset = struct.unpack("<II", infile.read(8))

                internal_title = common.read_string(infile, internal_title_offset - 0xfff80)
                title = common.read_string(infile, title_offset - 0xfff80)

                infile.seek(0x08, 1)
                difficulties = struct.unpack("<BBBBBB", infile.read(6))

                if len(title) == 0:
                    title = "%d" % i

                infile.seek(0x04, 1)
                video_idx = struct.unpack("<H", infile.read(2))[0]

                infile.seek(0x0c, 1)
                infile.seek(0x02, 1)
                # video_idx2 = struct.unpack("<H", infile.read(2))[0]

                videos_idx = [video_idx]

                infile.seek(0x0a, 1)
                overlay_palette = struct.unpack("<H", infile.read(2))[0]

                infile.seek(0x0c, 1)

                overlay_idxs = []

                for _ in range(0x16 // 4):
                    overlay_type, overlay_idx = struct.unpack("<HH", infile.read(4))

                    if overlay_type != 0:
                        overlay_idxs.append(overlay_idx)

                infile.seek(2, 1)

                charts_idx = struct.unpack("<IIIIIIII", infile.read(0x20))
                sounds_idx = struct.unpack("<HHHHHHHHHHHHHHHH", infile.read(0x20))
                overlay_idx = struct.unpack("<H", infile.read(0x02))[0]

                package_metadata = {
                    'song_id': i,
                    'title': title,
                    'title_ascii': internal_title,
                    'charts': {
                        'sp_beginner': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[4] if difficulties[4] != 0 else None,
                        },
                        'sp_normal': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[2] if difficulties[2] != 0 else None,
                        },
                        'sp_hyper': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[0] if difficulties[0] != 0 else None,
                        },
                        'sp_another': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[0] if difficulties[0] != 0 else None,
                        },
                        'dp_beginner': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[5] if difficulties[5] != 0 else None,
                        },
                        'dp_normal': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[3] if difficulties[3] != 0 else None,
                        },
                        'dp_hyper': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[1] if difficulties[1] != 0 else None,
                        },
                        'dp_another': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[1] if difficulties[1] != 0 else None,
                        },
                    },
                    'videos': [],
                    'overlays': None,
                }

                for index, file_index in enumerate(videos_idx):
                    if file_index == 0xffff:
                        # Invalid
                        continue

                    for index2, file_index2 in enumerate(videos_idx):
                        if index2 != index and file_index2 == file_index:
                            index = index2
                            break

                    if file_index >= 138:
                        file_index += 138

                    file_entries[file_index]['entries'] = i
                    file_entries[file_index]['references'].append({
                        'filename': "%s [%d].mpg" % (title, index),
                        'song_id': i,
                        'title': title
                    })

                    package_metadata['videos'].append("%s [%d].mpg" % (title, index))

                if overlay_idx not in [0xffff, 0x00]:
                    if overlay_idx >= 138:
                        overlay_idx += 138

                    overlay_filename = "%s.if" % title
                    file_entries[overlay_idx]['overlays'] = {
                        'exe': executable_filename,
                        'palette': overlay_palette,
                        'indexes': overlay_idxs
                    }
                    file_entries[overlay_idx]['song_id'] = i
                    file_entries[overlay_idx]['title'] = title
                    file_entries[overlay_idx]['references'].append({
                        'filename': overlay_filename,
                        'song_id': i,
                        'title': title
                    })

                    package_metadata['overlays'] = overlay_filename

                for index, file_index in enumerate(charts_idx):
                    if file_index == 0xffffffff or file_index == 0:
                        # Invalid
                        continue

                    file_index = (file_index & 0x0fffffff) + 138
                    file_entries[file_index]['compression'] = common.decode_lz
                    file_entries[file_index]['references'].append({
                        'filename': "%s [%s].ply" % (title, common.DIFFICULTY_MAPPING.get(index, str(index))),
                        'song_id': i,
                        'title': title
                    })

                    package_metadata['charts'][common.DIFFICULTY_MAPPING.get(index, str(index)).lower().replace(" ", "_")]['filename'] = "%s [%s].ply" % (title, common.DIFFICULTY_MAPPING.get(index, str(index)))

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

                        if file_index == 0xffff:
                            # Invalid
                            continue

                        if file_index >= 138:
                            file_index += 138

                        for pair_index2, pair2 in enumerate(sound_pairs):
                            if pair_index2 != pair_index and pair2[1] == pair[0]:
                                pair_index = pair_index2
                                break

                        if is_keysound:
                            file_entries[file_index]['references'].append({
                                'filename': "%s [%d].wvb" % (title, pair_index),
                                'song_id': i,
                                'title': title
                            })

                            package_metadata['charts'][common.DIFFICULTY_MAPPING.get(pair_index, str(pair_index)).lower().replace(" ", "_")]['sounds'] = "%s [%d].wvb" % (title, pair_index)

                        else:
                            file_entries[file_index]['references'].append({
                                'filename': "%s [%d].pcm" % (title, pair_index),
                                'song_id': i,
                                'title': title
                            })

                            package_metadata['charts'][common.DIFFICULTY_MAPPING.get(pair_index, str(pair_index)).lower().replace(" ", "_")]['bgm'] = "%s [%d].pcm" % (title, pair_index)

                song_metadata[i] = package_metadata

        return file_entries, song_metadata


    @staticmethod
    def extract(exe_filename, input_folder, output_folder, raw_mode, conversion_mode):
        main_archive_file_entries = []
        main_archive_file_entries += filetable_readers.filetable_reader_old2(exe_filename, os.path.join(input_folder, "DX2_7", "BM2DX7B.BIN"), 0x1b7460, 0x8a0 // 16, len(main_archive_file_entries))
        main_archive_file_entries += filetable_readers.filetable_reader_old2(exe_filename, os.path.join(input_folder, "DX2_7", "BM2DX7C.BIN"), 0x1b9a30, 0x2bc0 // 16, len(main_archive_file_entries))
        main_archive_file_entries += filetable_readers.filetable_reader_old2(exe_filename, os.path.join(input_folder, "DX2_7", "BM2DX7A.BIN"), 0x1b6a50, 0xa10 // 16, len(main_archive_file_entries))

        _, song_metadata = Iidx7thCsHandler.read_songlist(exe_filename, 0x1c1af0, 0x3840 // 0xa0, main_archive_file_entries)

        common.extract_files(main_archive_file_entries, output_folder, raw_mode)

        if conversion_mode and not raw_mode:
            common.extract_songs(main_archive_file_entries, output_folder, '7thcs', song_metadata)

        common.extract_overlays(main_archive_file_entries, output_folder, { # 7th
            'base_offset': 0xfff80,
            'palette_table': 0xf66b0,
            'animation_table': 0xf68d0,
            'animation_data_table': 0xfa9a0,
            'tile_table': 0x111610,
            'animation_parts_table': 0x1aec50,
        })


def get_class():
    return Iidx7thCsHandler
