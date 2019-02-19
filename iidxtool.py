import argparse
import glob
import importlib
import os
import sys

import charttool.plugins


def find_handler(input_filename, input_format):
    formats = [importlib.import_module('charttool.plugins.' + name).get_class() for name in charttool.plugins.__all__]

    for handler in formats:
        if input_format is not None and handler.get_format_name().lower() == input_format.lower():
            return handler

    return None


def process_file(params):
    input_format = params['input_format'] if 'input_format' in params else None
    output_format = params['output_format'] if 'output_format' in params else None

    input_handler = find_handler(None, input_format)
    output_handler = find_handler(None, output_format)

    if output_handler is None:
        output_handler = input_handler

    if input_handler is None:
        print("Could not find a handler for input file")
        exit(1)

    if output_handler is None:
        print("Could not find a handler for output file")
        exit(1)

    print("Using {} handler to process this file...".format(input_handler.get_format_name()))

    json_data = input_handler.to_json(params)

    params['input'] = json_data
    output_handler.to_chart(params)


def main(args):
    parser = argparse.ArgumentParser()
    input_group = parser.add_argument_group('input')
    input_group.add_argument('--input', help='Input file/folder')
    input_group.add_argument('--input-format', help='Input file format version', required=True)

    input_chart_group = parser.add_argument_group('input_chart')
    for part in ['sp', 'dp']:
        for difficulty in ['beginner', 'normal', 'hyper', 'another', 'black']:
            input_chart_group.add_argument('--input-%s-%s' % (part, difficulty), help="%s %s chart input (for creation)" % (part.upper(), difficulty))

    parser.add_argument('--output', help='Output file/folder (only usable with some converters)')
    parser.add_argument('--output-format', help='Output file format version', required=True)

    # Uncomment when/if old PS2 chart writers are implemented
    # output_chart_group = parser.add_argument_group('output_chart')
    # for part in ['sp', 'dp']:
    #     for difficulty in ['beginner', 'normal', 'hyper', 'another', 'black']:
    #         output_chart_group.add_argument('--output-%s-%s' % (part, difficulty), help="%s %s chart input (for creation, only usable with some converters)" % (part.upper(), difficulty))

    args = parser.parse_args(args)

    if args.input and os.path.isdir(args.input):
        for filename in glob.glob(glob.escape(args.input) + "\\*.ply"):
            for part in ['sp', 'dp']:
                for difficulty in ['beginner', 'normal', 'hyper', 'another', 'black']:
                    if '[{} {}]'.format(part, difficulty).upper() in filename:
                        setattr(args, 'input_{}_{}'.format(part, difficulty), filename)
                        break

        args.input = None

    params = {
        "input": args.input if args.input else None,
        "input_format": args.input_format if args.input_format else None,
        "output": args.output,
        "output_format": args.output_format,
        'input_charts': {},
        'output_charts': {},
    }

    last_filename = args.input
    for part in ['sp', 'dp']:
        for difficulty in ['beginner', 'normal', 'hyper', 'another', 'black']:
            val = getattr(args, 'input_{}_{}'.format(part, difficulty))

            if val is not None:
                params['input_charts']['{} {}'.format(part, difficulty).upper()] = val
                last_filename = val

    if not args.output:
        args.output = os.path.join(os.path.dirname(last_filename), "output.json") # TODO: Detect proper extension
        params['output'] = args.output

    # for part in ['sp', 'dp']:
    #     for difficulty in ['beginner', 'normal', 'hyper', 'another', 'black']:
    #         val = getattr(args, 'output_{}_{}'.format(part, difficulty))

    #         if val is not None:
    #             params['output_charts']['{} {}'.format(part, difficulty).upper()] = val

    process_file(params)



if __name__ == "__main__":
    main(sys.argv[1:])