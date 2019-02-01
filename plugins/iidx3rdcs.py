import json
import os
import struct

import common
import filetable_readers


class Iidx3rdCsHandler:
    @staticmethod
    def is_match(filename):
        return filename == "SLPM_650.06"


    @staticmethod
    def read_songlist(executable_filename, songlist_offset, songlist_count, file_entries):
        with open(executable_filename, "rb") as infile:
            chart_data_buffer = infile.read()

            infile.seek(songlist_offset)

            for i in range(songlist_count):
                infile.seek(songlist_offset + i * 0x7c, 0)

                internal_title_offset, title_offset = struct.unpack("<II", infile.read(8))

                internal_title = common.read_string(infile, internal_title_offset - 0xff000)
                title = common.read_string(infile, title_offset - 0xff000)

                if len(title) == 0:
                    title = "%d" % i

                infile.seek(0x02, 1)
                video_idx = struct.unpack("<H", infile.read(2))[0]
                video_idx2 = video_idx + 1

                infile.seek(0x1c, 1)
                overlay_palette = struct.unpack("<H", infile.read(2))[0]

                infile.seek(0x0a, 1)
                overlay_idxs = []
                for i in range(0x1e // 6):
                    overlay_type, overlay_idx, unk = struct.unpack("<HHH", infile.read(6))

                    if overlay_type != 0:
                        overlay_idxs.append(overlay_idx)

                infile.seek(0x02, 1)

                charts_idx = struct.unpack("<IIIIII", infile.read(0x18))
                sounds_idx = struct.unpack("<HH", infile.read(0x04))
                bgm_idx = struct.unpack("<HHH", infile.read(0x06))
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

                for index, file_index in enumerate(sounds_idx):
                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    file_entries[file_index]['real_filename'].append("%s [%d].wvb" % (title, index))
                    file_entries[file_index]['song_id'] = i

                for index, file_index in enumerate(bgm_idx):
                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    file_entries[file_index]['real_filename'].append("%s [%d].pcm" % (title, index))
                    file_entries[file_index]['song_id'] = i

        return file_entries


    @staticmethod
    def extract(exe_filename, input_folder, output_folder, raw_mode, conversion_mode):
        main_archive_file_entries = []
        main_archive_file_entries += filetable_readers.filetable_reader_old(exe_filename, os.path.join(input_folder, "DX2_3", "BM2DX3.BIN"), 0x145cd0, 0x1050 // 12, len(main_archive_file_entries))

        Iidx3rdCsHandler.read_songlist(exe_filename, 0x77fc8, 0x27b8 // 0x7c, main_archive_file_entries)

        common.extract_files(main_archive_file_entries, output_folder, raw_mode)

        common.extract_overlays(main_archive_file_entries, output_folder, { # 3rd
            'base_offset': 0xff000,
            'palette_table': 0x13d128,
            'animation_table': 0x7ac70,
            'animation_data_table': 0x7df48,
            'tile_table': 0x94ff8,
            'animation_parts_table': 0x130ac8,
        })


def get_class():
    return Iidx3rdCsHandler
