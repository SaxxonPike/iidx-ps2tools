import argparse
import importlib
import os

import plugins

def find_handler(exe_filename):
    formats = [importlib.import_module('plugins.' + name).get_class() for name in plugins.__all__]

    base_exe_filename = os.path.basename(exe_filename).upper()

    for handler in formats:
        if exe_filename and handler.is_match(base_exe_filename):
            return handler

    return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-exe', help='Input PS2 executable file', required=True)
    parser.add_argument('--input-folder', help='Input folder', required=True)
    parser.add_argument('--output', help='Output folder', required=True)
    args = parser.parse_args()

    handler = find_handler(args.input_exe)
    handler.extract(args.input_exe, args.input_folder, args.output)
