import base64
import json
import os
import struct
import sys

from iidx_common import COMMAND_MAPPING, COMMAND_MAPPING_REVERSE, create_event_ps2

def chart_to_json(input_filename):
    events = []

    if not input_filename or not os.path.exists(input_filename):
        return None

    with open(input_filename, "rb") as infile:
        chart_offset = struct.unpack("<I", infile.read(4))[0]

        if chart_offset != 4:
            timestamp_multiplier = struct.unpack("<I", infile.read(4))[0]
        else:
            # Does this ever occur?
            timestamp_multiplier = 0x414c

        infile.seek(chart_offset)

        events = {}

        while True:
            offset, c1, param = struct.unpack("<HBB", infile.read(4))

            if offset == 0x7fff:
                break

            offset = round((offset * timestamp_multiplier) / 1000)

            event = create_event_ps2(offset, c1, None, param)

            if event['offset'] not in events:
                events[event['offset']] = []

            events[event['offset']].append(event)

    return events


class Iidx5thCsFormat:
    @staticmethod
    def get_format_name():
        return "5thcs"


    @staticmethod
    def to_json(params):
        # Create final output
        output = {
            'metadata': {
                'version': Iidx5thCsFormat.get_format_name(),
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
    return Iidx5thCsFormat
