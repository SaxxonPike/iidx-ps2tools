import json
import os
import struct

import common
import filetable_readers

from plugins.iidx16thempresscs import Iidx16thEmpressCsHandler

class Iidx16thPremiumBestCsHandler:
    @staticmethod
    def is_match(filename):
        return filename == "SLPM_552.22"


    @staticmethod
    def extract(exe_filename, input_folder, output_folder):
        main_archive_file_entries = []
        main_archive_file_entries += filetable_readers.filetable_reader_modern2(exe_filename, os.path.join(input_folder, "bm2dx16a.dat"), 0x140e90, 0x2a0 // 12, len(main_archive_file_entries))
        main_archive_file_entries += filetable_readers.filetable_reader_modern2(exe_filename, os.path.join(input_folder, "bm2dx16b.dat"), 0x141130, 0x28f8 // 12, len(main_archive_file_entries))
        main_archive_file_entries += filetable_readers.filetable_reader_modern2(exe_filename, os.path.join(input_folder, "bm2dx16c.dat"), 0x143a28, 0x660 // 12, len(main_archive_file_entries))

        animation_file_entries = filetable_readers.dat_filetable_reader_modern(exe_filename, os.path.join(input_folder, "data1.dat"), 0x139980, 0x5bd0 // 16)

        Iidx16thEmpressCsHandler.read_songlist(exe_filename, 0x17e0f0, 0x7850 // 0x134, main_archive_file_entries, animation_file_entries)

        common.extract_files(main_archive_file_entries, output_folder)
        common.extract_files(animation_file_entries, output_folder)
        common.extract_overlays(animation_file_entries, output_folder, None)


def get_class():
    return Iidx16thPremiumBestCsHandler
