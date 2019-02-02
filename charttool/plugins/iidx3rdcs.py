import base64
import json
import os
import struct
import sys

from charttool.iidx_common import COMMAND_MAPPING, COMMAND_MAPPING_REVERSE, create_event_ps2

TIMESTAMP_MULTIPLIER = 0x414c # Does this change? Look at game code

def chart_to_json(input_filename):
    events = {}

    if not input_filename or not os.path.exists(input_filename):
        return None

    with open(input_filename, "rb") as infile:
        while True:
            offset, c1, param = struct.unpack("<HBB", infile.read(4))

            if offset == 0x7fff:
                break

            orig_offset = offset
            offset = round((offset * TIMESTAMP_MULTIPLIER) / 1000)

            event = create_event_ps2(offset, c1, None, param)

            if event['offset'] not in events:
                events[event['offset']] = []

            events[event['offset']].append(event)

    return events


class Iidx3rdCsFormat:
    @staticmethod
    def get_format_name():
        return "3rdcs"


    @staticmethod
    def to_json(params):
        # Create final output
        output = {
            'metadata': {
                'version': Iidx3rdCsFormat.get_format_name(),
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
    return Iidx3rdCsFormat
