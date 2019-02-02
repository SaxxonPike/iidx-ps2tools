import base64
import ctypes
import json
import os
import struct
import sys
from collections import OrderedDict

from charttool.iidx_common import COMMAND_MAPPING, COMMAND_MAPPING_REVERSE, IIDX_AC_DIFFICULTY_MAPPING, IIDX_AC_DIFFICULTY_MAPPING_REVERSE, ac_parse_file

def chart_to_json(infile, chart_offset, chart_size):
    infile.seek(chart_offset)

    events = OrderedDict()

    while True:
        offset = struct.unpack("<I", infile.read(4))[0]

        if offset == 0x7fffffff:
            break

        command, command_param, param = struct.unpack("<BBH", infile.read(4))

        if command not in COMMAND_MAPPING:
            print("%08x | %04x %02x %02x %04x" % (infile.tell() - 8, offset, command, command_param, param))
            print("Unknown command")
            exit(1)

        event_name = COMMAND_MAPPING[command]

        event = {
            'offset': offset,
            'event': event_name,
        }

        if event_name in ['note_p1', 'note_p2']:
            # Note
            event.update({
                'slot': command_param,
                'value': param,
            })

        elif event_name in ['sample_p1', 'sample_p2']:
            # Sample load
            event.update({
                'slot': command_param,
                'sound_id': param,
            })

        elif event_name == "bpm":
            # BPM
            event.update({
                'misc': command_param,
                'bpm': param
            })

        elif event_name == "timesig":
            # Time signature
            event.update({
                'numerator': command_param,
                'denominator': param,
            })

        elif event_name == "auto":
            # Autoplay Note
            event.update({
                'slot': command_param,
                'sound_id': param,
            })

        elif event_name == "timing":
            # Timing
            event.update({
                'slot': command_param,
                'judgement': ctypes.c_byte(param).value,
            })

        elif event_name == "notes":
            # Note count
            event.update({
                'player': command_param,
                'notes': param,
            })

        elif event_name == "measure":
            # Measure marker
            event.update({
                'player': command_param,
            })

        elif event_name == "end":
            # End of chart
            event.update({
                'player': command_param,
            })

        if event['offset'] not in events:
            events[event['offset']] = []

        events[event['offset']].append(event)

    return events


class Iidx25thAcFormat:
    @staticmethod
    def get_format_name():
        return "25thac"

    @staticmethod
    def to_json(params):
        input_filename = params.get('input')

        if not input_filename or not os.path.exists(input_filename):
            return None

        with open(input_filename, "rb") as infile:
            output = ac_parse_file(infile, chart_to_json)
            output['version'] = Iidx25thAcFormat.get_format_name()

            return json.dumps(output, indent=4, sort_keys=True)


    @staticmethod
    def to_chart(params):
        json_chart = json.loads(params['input']) if 'input' in params else None
        output_filename = params.get('output', "")

        charts_by_difficulty = {}

        for chart in json_chart.get('charts', []):
            output = bytearray()

            for events_by_offset_key in sorted([int(x) for x in chart.get('events', {}).keys()]):
                events_by_offset_key = str(events_by_offset_key)
                for event in chart['events'][events_by_offset_key]:
                    event_name = event['event'].lower()

                    if event_name not in COMMAND_MAPPING_REVERSE:
                        print("Unknown event:")
                        print(event)
                        exit(1)

                    if event_name in ['note_p1', 'note_p2'] and event['offset'] == 0:
                        continue

                    output += struct.pack("<I", event['offset'])
                    output += struct.pack("<B", COMMAND_MAPPING_REVERSE[event_name])

                    if event_name in ['note_p1', 'note_p2', 'sample_p1', 'sample_p2', 'auto']:
                        output += struct.pack("<B", event.get('slot', 0))
                        output += struct.pack("<H", event.get('sound_id', 0))

                    elif event_name == "bpm":
                        # BPM
                        output += struct.pack("<B", event.get('misc', 0))
                        output += struct.pack("<H", event.get('bpm', 0))

                    elif event_name == "timesig":
                        # Time signature
                        output += struct.pack("<B", event.get('numerator', 4))
                        output += struct.pack("<H", event.get('denominator', 4))

                    elif event_name == "timing":
                        # Judgement
                        output += struct.pack("<B", event.get('slot', 0))
                        output += struct.pack("<H", ctypes.c_ubyte(event.get('judgement', 0)).value)

                    elif event_name == "notes":
                        # Note count
                        output += struct.pack("<B", event.get('player', 0))
                        output += struct.pack("<H", event.get('notes', 0))

                    elif event_name == "measure":
                        # Note count
                        output += struct.pack("<B", event.get('player', 0))
                        output += struct.pack("<H", 0)

                    elif event_name == "end":
                        # Note count
                        output += struct.pack("<B", event.get('player', 0))
                        output += struct.pack("<H", 0)

                    else:
                        output += struct.pack("<B", 0)
                        output += struct.pack("<H", 0)

            output += struct.pack("<I", 0x7fffffff)
            output += struct.pack("<I", 0)

            charts_by_difficulty[chart.get('chart_type', '')] = output

        chart_header_info = [[None, None]] * (0x60 // 8)

        output_body = bytearray()

        for k in ['SP NORMAL', 'DP NORMAL', 'SP ANOTHER', 'DP ANOTHER', 'SP HYPER', 'DP HYPER']:
            if k in charts_by_difficulty:
                chart_header_info[IIDX_AC_DIFFICULTY_MAPPING_REVERSE[k]] = [len(output_body), len(charts_by_difficulty[k])]
                output_body += charts_by_difficulty[k]

        with open(output_filename, "wb") as f:
            # Write header
            for info in chart_header_info:
                offset, size = info

                if offset is not None:
                    offset += len(chart_header_info) * 8
                else:
                    offset = 0
                    size = 0

                f.write(struct.pack("<II", offset, size))

            f.write(output_body)


def get_class():
    return Iidx25thAcFormat
