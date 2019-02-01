import json
import os
import struct

import common
import filetable_readers

from plugins.iidx9thcs import Iidx9thCsHandler

class Iidx10thCsHandler:
    @staticmethod
    def is_match(filename):
        return filename == "SLPM_661.80"


    @staticmethod
    def read_songlist(executable_filename, songlist_offset, songlist_count, file_entries, animation_file_entries):
        return Iidx9thCsHandler.read_songlist(executable_filename, songlist_offset, songlist_count, file_entries, animation_file_entries)


    @staticmethod
    def extract(exe_filename, input_folder, output_folder, raw_mode, conversion_mode):
        main_archive_file_entries = []
        main_archive_file_entries += filetable_readers.filetable_reader_modern(exe_filename, os.path.join(input_folder, "DATA2.DAT"), 0xcdc90, 0x1a38 // 8, len(main_archive_file_entries))

        animation_file_entries = filetable_readers.dat_filetable_reader_modern(exe_filename, os.path.join(input_folder, "DATA1.DAT"), 0xc8e08, 0x11b0 // 16)

        Iidx10thCsHandler.read_songlist(exe_filename, 0x10bae0, 0x7d20 // 0x16c, main_archive_file_entries, animation_file_entries)

        common.extract_files(main_archive_file_entries, output_folder, raw_mode)
        common.extract_files(animation_file_entries, output_folder, raw_mode, conversion_mode, len(main_archive_file_entries))
        common.extract_overlays(animation_file_entries, output_folder, None)


def get_class():
    return Iidx10thCsHandler
