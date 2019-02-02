import json
import os
import struct

import common
import filetable_readers


class Iidx4thCsHandler:
    @staticmethod
    def is_match(filename):
        return filename == "SLPM_650.26"


    @staticmethod
    def read_songlist(executable_filename, songlist_offset, songlist_count, file_entries):
        song_metadata = {}

        with open(executable_filename, "rb") as infile:
            chart_data_buffer = infile.read()

            infile.seek(songlist_offset)

            for i in range(songlist_count):
                infile.seek(songlist_offset + i * 0x90, 0)

                internal_title_offset, title_offset = struct.unpack("<II", infile.read(8))

                internal_title = common.read_string(infile, internal_title_offset - 0xff000)
                title = common.read_string(infile, title_offset - 0xff000)

                infile.seek(0x01, 1)
                difficulties = struct.unpack("<BB", infile.read(2))

                if len(title) == 0:
                    title = "%d" % i

                infile.seek(0x03, 1)
                video_idx = struct.unpack("<H", infile.read(2))[0]
                videos_idx = [video_idx]

                if video_idx != 0xffff:
                    videos_idx.append(video_idx+1)

                infile.seek(0x1c, 1)
                overlay_palette = struct.unpack("<H", infile.read(2))[0]

                infile.seek(0x0a, 1)
                overlay_idxs = []
                for _ in range(0x1e // 6):
                    overlay_type, overlay_idx, unk = struct.unpack("<HHH", infile.read(6))

                    if overlay_type != 0:
                        overlay_idxs.append(overlay_idx)

                infile.seek(0x02, 1)

                charts_idx = struct.unpack("<IIIIII", infile.read(0x18))
                sounds_idx = struct.unpack("<HHHHHHHHHHHH", infile.read(0x18))
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
                            'difficulty': difficulties[1] if difficulties[1] != 0 else None,
                        },
                        'sp_normal': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[1] if difficulties[1] != 0 else None,
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
                        'sp_black': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[0] if difficulties[0] != 0 else None,
                        },
                        'dp_beginner': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[1] if difficulties[1] != 0 else None,
                        },
                        'dp_normal': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[1] if difficulties[1] != 0 else None,
                        },
                        'dp_hyper': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[0] if difficulties[0] != 0 else None,
                        },
                        'dp_another': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[0] if difficulties[0] != 0 else None,
                        },
                        'dp_black': {
                            'filename': None,
                            'sounds': None,
                            'bgm': None,
                            'difficulty': difficulties[0] if difficulties[0] != 0 else None,
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

                    file_entries[file_index]['entries'] = i
                    file_entries[file_index]['references'].append({
                        'filename': "%s [%d].mpg" % (title, index),
                        'song_id': i,
                        'title': title
                    })

                    package_metadata['videos'].append("%s [%d].mpg" % (title, index))

                if overlay_idx not in [0xffff, 0x00]:
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

                    file_entries.append({
                        'filename': executable_filename,
                        'offset': file_index-0xff000,
                        'size': len(chart_data_buffer) - file_index-0xff000,
                        'compression': common.decode_lz,
                        'references': [{
                            'filename': "%s [%s].ply" % (title, common.DIFFICULTY_MAPPING.get(index, str(index))),
                            'song_id': i,
                            'title': title
                        }]
                    })

                    package_metadata['charts'][common.DIFFICULTY_MAPPING.get(index, str(index)).lower().replace(" ", "_")]['filename'] = "%s [%s].ply" % (title, common.DIFFICULTY_MAPPING.get(index, str(index)))

                sound_pairs = [
                    [sounds_idx[0], sounds_idx[2]],
                    [sounds_idx[1], sounds_idx[3]],
                    [sounds_idx[4], sounds_idx[6]],
                    [sounds_idx[5], sounds_idx[7]],
                    [sounds_idx[8], sounds_idx[10]],
                    [sounds_idx[9], sounds_idx[11]],
                ]

                for pair_index, pair in enumerate(sound_pairs):
                    for index, file_index in enumerate(pair):
                        is_keysound = index == 0

                        if file_index == 0xffff:
                            # Invalid
                            continue

                        print(file_index)

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
        main_archive_file_entries += filetable_readers.filetable_reader_old(exe_filename, os.path.join(input_folder, "DX2_4", "BM2DX4.BIN"), 0x137450, 0x9d8 // 12, len(main_archive_file_entries))

        _, song_metadata = Iidx4thCsHandler.read_songlist(exe_filename, 0x8bc98, 0x2010 // 0x90, main_archive_file_entries)

        common.extract_files(main_archive_file_entries, output_folder, raw_mode)

        if conversion_mode and not raw_mode:
            common.extract_songs(main_archive_file_entries, output_folder, '4thcs', song_metadata)

        common.extract_overlays(main_archive_file_entries, output_folder, { # 4th
            'base_offset': 0xff000,
            'palette_table': 0x12b4f0,
            'animation_table': 0x8e108,
            'animation_data_table': 0x91640,
            'tile_table': 0xa6a80,
            'animation_parts_table': 0x11ec50,
        })


def get_class():
    return Iidx4thCsHandler
