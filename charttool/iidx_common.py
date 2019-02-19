import ctypes
import struct

IIDX_AC_DIFFICULTY_MAPPING = {
    0: 'SP NORMAL',
    1: 'SP HYPER',
    2: 'SP ANOTHER',
    6: 'DP NORMAL',
    7: 'DP HYPER',
    8: 'DP ANOTHER',
}

IIDX_AC_DIFFICULTY_MAPPING_REVERSE = {v: k for k, v in IIDX_AC_DIFFICULTY_MAPPING.items()}

COMMAND_MAPPING = {
    0x00: 'note_p1',
    0x01: 'note_p2',
    0x02: 'sample_p1',
    0x03: 'sample_p2',
    0x04: 'bpm',
    0x05: 'timesig',
    0x06: 'end',
    0x07: 'auto',
    0x08: 'timing',
    0x0b: 'unk',
    0x0c: 'measure',
    0x10: 'notes',
}

COMMAND_MAPPING_REVERSE = {v: k for k, v in COMMAND_MAPPING.items()}

def ac_parse_file(infile, callback):
    chart_offsets = []

    for i in range(0, 0x60 // 8):
        chart_offsets.append(struct.unpack("<II", infile.read(8)))

    # Create final output
    output = {
        'metadata': {
            'chartid': "", # 01000 etc
            'title': "", # 5.1.1. etc
            'artist': "", # kors k etc
            'genre': "", # Ambient etc
            'difficulty': "", # level 10 etc
        },
        'charts': []
    }

    for chart_idx, chart_info in enumerate(chart_offsets):
        chart_offset, chart_size = chart_info

        if chart_offset == 0 or chart_size == 0:
            continue

        chart_data = callback(infile, chart_offset, chart_size)

        output['charts'].append({
            'chart_type': IIDX_AC_DIFFICULTY_MAPPING[chart_idx],
            'events': chart_data
        })

    return output


def create_event_ps2(offset, c1, c2, param):
    offset = int(offset)

    if c2 == None:
        c2 = param

    command = c1 & 0x0f
    command_param = c1 >> 4

    if command not in COMMAND_MAPPING:
        print("Unkonwn command: %02x @ %08x" % (command, offset))
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
            'value': 0,
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
            'bpm': c2,
        })

    elif event_name == "timesig":
        # Time signature
        event.update({
            'numerator': c2,
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
            'judgement': ctypes.c_byte(c2).value,
        })

    return event
