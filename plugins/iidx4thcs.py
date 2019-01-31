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
        with open(executable_filename, "rb") as infile:
            chart_data_buffer = infile.read()

            infile.seek(songlist_offset)

            for i in range(songlist_count):
                infile.seek(songlist_offset + i * 0x90, 0)

                internal_title_offset, title_offset = struct.unpack("<II", infile.read(8))

                internal_title = common.read_string(infile, internal_title_offset - 0xff000)
                title = common.read_string(infile, title_offset - 0xff000)

                infile.seek(0x06, 1)
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
                sounds_idx_1 = struct.unpack("<HH", infile.read(0x04))
                bgms_idx_1 = struct.unpack("<HHHHHH", infile.read(0x0c))
                sounds_idx_2 = struct.unpack("<HH", infile.read(0x04))
                bgms_idx_2 = struct.unpack("<HH", infile.read(0x04))
                overlay_idx = struct.unpack("<H", infile.read(0x02))[0]

                if video_idx not in [0xffff, 0x00]:
                    file_entries[video_idx]['real_filename'].append("%s [0].mpg" % title)
                    file_entries[video_idx+1]['real_filename'].append("%s [1].mpg" % title)

                if overlay_idx not in [0xffff, 0x00]:
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

                    file_entries.append({
                        'filename': executable_filename,
                        'offset': file_index-0xff000,
                        'size': len(chart_data_buffer) - file_index-0xff000,
                        'compression': common.decode_lz,
                        'real_filename': [
                            "%s [%s].ply" % (title, common.OLD_DIFFICULTY_MAPPING.get(index, str(index)))
                        ],
                        'file_id': len(file_entries)
                    })

                for index, file_index in enumerate(sounds_idx_1):
                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    file_entries[file_index]['real_filename'].append("%s [0-%d].wvb" % (title, index))

                for index, file_index in enumerate(bgms_idx_1):
                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    file_entries[file_index]['real_filename'].append("%s [0-%d].pcm" % (title, index))

                for index, file_index in enumerate(sounds_idx_2):
                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    file_entries[file_index]['real_filename'].append("%s [1-%d].wvb" % (title, index))

                for index, file_index in enumerate(bgms_idx_2):
                    if file_index == 0xffff or file_index == 0x00:
                        # Invalid
                        continue

                    print("%08x" % infile.tell(), file_index, len(file_entries))

                    file_entries[file_index]['real_filename'].append("%s [1-%d].pcm" % (title, index))

        return file_entries


    @staticmethod
    def extract(exe_filename, input_folder, output_folder):
        main_archive_file_entries = []
        main_archive_file_entries += filetable_readers.filetable_reader_old(exe_filename, os.path.join(input_folder, "DX2_4", "BM2DX4.BIN"), 0x137450, 0x9d8 // 12, len(main_archive_file_entries))

        Iidx4thCsHandler.read_songlist(exe_filename, 0x8bc98, 0x2010 // 0x90, main_archive_file_entries)

        common.extract_files(main_archive_file_entries, output_folder)

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
