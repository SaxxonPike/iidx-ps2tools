import base64
import json
import os
import struct
import sys

from charttool.iidx_common import COMMAND_MAPPING, COMMAND_MAPPING_REVERSE, create_event_ps2

def chart_to_json(input_filename):
    if not input_filename or not os.path.exists(input_filename):
        return None

    print(input_filename)
    with open(input_filename, "rb") as infile:
        chart_offset = struct.unpack("<I", infile.read(4))[0]

        if chart_offset != 4:
            timestamp_multiplier = struct.unpack("<I", infile.read(4))[0] - 10 # Not sure why -10 but it seems to work better
        else:
            # Does this ever occur?
            timestamp_multiplier = 0x414c

        infile.seek(chart_offset)

        events = {}

        while True:
            offset = struct.unpack("<I", infile.read(4))[0]

            if offset == 0x7fff:
                break

            c1, c2, param = struct.unpack("<BBH", infile.read(4))

            offset = (offset * timestamp_multiplier) / 1000

            event = create_event_ps2(offset, c1, c2, param)

            if event['offset'] not in events:
                events[event['offset']] = []

            events[event['offset']].append(event)

    return events


class Iidx7thCsFormat:
    @staticmethod
    def get_format_name():
        return "7thcs"


    @staticmethod
    def to_json(params):
        # Create final output
        output = {
            'metadata': {
                'version': Iidx7thCsFormat.get_format_name(),
                'chartid': "",
                'title': "",
                'artist': "",
                'genre': "",
                'difficulty': "",
            },
            'charts': []
        }

        charts = params.get('input_charts', {})
        charts[''] = params.get('input', None)

        for k in charts:
            if charts[k] is not None:
                chart_data = chart_to_json(charts[k])
                output['charts'].append({
                    'chart_type': k,
                    'events': chart_data
                })

        return json.dumps(output, indent=4, sort_keys=True)


    @staticmethod
    def to_chart(params):
        raise NotImplemented("This conversion is not supported")


def get_class():
    return Iidx7thCsFormat
