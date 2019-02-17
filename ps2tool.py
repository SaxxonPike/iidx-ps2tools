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
    parser.add_argument('--input-folder', help='Input folder (if not set, uses the input EXE path')
    parser.add_argument('--output', help='Output folder', required=True)
    parser.add_argument('--convert-overlay', help="Convert overlays (can't be used with raw mode)", action="store_true")
    parser.add_argument('--convert-song', help="Convert songs (can't be used with raw mode)", action="store_true")
    parser.add_argument('--raw', help="Raw extraction mode (can't be used with conversion mode)", action="store_true")
    args = parser.parse_args()

    if not args.input_folder:
        args.input_folder = os.path.dirname(args.input_exe)

    conversion_mode = []
    if args.convert_overlay:
        args.raw = False
        conversion_mode.append('overlay')

    if args.convert_song:
        args.raw = False
        conversion_mode.append('song')

    elif args.raw:
        args.convert = False

    handler = find_handler(args.input_exe)
    handler.extract(args.input_exe, args.input_folder, args.output, args.raw, conversion_mode)
