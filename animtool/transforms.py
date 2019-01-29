# pylint: disable=missing-docstring

import copy
import ctypes
import struct

def pad_transform_data(data, end_frame):
    output = data

    keys = sorted(data.keys())
    if keys:
        for j in range(0, sorted(output.keys())[0]):
            output[j] = copy.deepcopy(data[keys[0]])
            output[j]['frame'] = j

        for j in range(output[sorted(output.keys())[-1]]['frame'], end_frame):
            output[j] = copy.deepcopy(data[keys[-1]])
            output[j]['frame'] = j

    return output


def read_variable_section(infile):
    data = []

    while True:
        data.append(infile.read(4))

        if data[-1] == b'\xff\xff\x00\x00':
            break

    return b''.join(data)


def read_data_block(infile, offset, end_frame, reader_callback, logic_callback, point_callback=None):
    if offset in [0x0000, 0xffff]:
        return {}

    cur_offset = infile.tell()
    infile.seek(offset)
    block_data = read_variable_section(infile)
    infile.seek(cur_offset)

    points = reader_callback(block_data)

    if not points:
        return {}

    output = {}
    for i in range(len(points) - 1):
        start_frame = points[i]['frame']
        end_frame = points[i+1]['frame']

        if start_frame == end_frame:
            continue

        for j in range(0, end_frame - start_frame):
            output[start_frame + j] = logic_callback(points, i, j, start_frame, end_frame)

    for point in points:
        if point_callback is not None:
            point = point_callback(point)

        output[point['frame']] = point

    import hexdump
    hexdump.hexdump(block_data)
    print(output)
    print()

    return pad_transform_data(output, end_frame)


def read_position_block(infile, offset, start_frame, end_frame):
    def reader_callback(data):
        points = []

        for i in range((len(data) - 4) // 8):
            frame, frame_x, frame_y, _ = struct.unpack("<HHHH", data[i*8:i*8+8])
            frame = ctypes.c_short(frame).value
            frame_x = ctypes.c_short(frame_x).value
            frame_y = ctypes.c_short(frame_y).value

            points.append({
                'frame': frame,
                'x': frame_x,
                'y': frame_y,
            })

        return points


    def logic_callback(points, i, j, start_frame, end_frame):
        frame_count = end_frame - start_frame

        x_diff = points[i+1]['x'] - points[i]['x']
        x_step = x_diff / frame_count

        y_diff = points[i+1]['y'] - points[i]['y']
        y_step = y_diff / frame_count

        cur_x = round(points[i]['x'] + x_step * j)
        cur_y = round(points[i]['y'] + y_step * j)

        return {
            'frame': start_frame + j,
            'x': cur_x,
            'y': cur_y,
        }

    return read_data_block(infile, offset, end_frame, reader_callback, logic_callback)


def read_zoom_block(infile, offset, start_frame, end_frame):
    def reader_callback(data):
        points = []

        for i in range((len(data) - 4) // 8):
            frame, scale_x, scale_y, _ = struct.unpack("<HHHH", data[i*8:i*8+8])
            frame = ctypes.c_short(frame).value
            scale_x = ctypes.c_short(scale_x).value
            scale_y = ctypes.c_short(scale_y).value

            points.append({
                'frame': frame,
                'scale_x': scale_x,
                'scale_y': scale_y,
            })

        return points


    def logic_callback(points, i, j, start_frame, end_frame):
        frame_count = end_frame - start_frame

        scale_x_diff = points[i+1]['scale_x'] - points[i]['scale_x']
        scale_x_step = scale_x_diff / frame_count

        scale_y_diff = points[i+1]['scale_y'] - points[i]['scale_y']
        scale_y_step = scale_y_diff / frame_count

        cur_scale_x = (points[i]['scale_x'] + scale_x_step * j) / 100
        cur_scale_y = (points[i]['scale_y'] + scale_y_step * j) / 100

        return {
            'frame': start_frame + j,
            'scale_x': cur_scale_x,
            'scale_y': cur_scale_y,
        }


    def point_callback(point):
        return {
            'frame': point['frame'],
            'scale_x': point['scale_x'] / 100,
            'scale_y': point['scale_y'] / 100,
        }

    return read_data_block(infile, offset, end_frame, reader_callback, logic_callback, point_callback)


def read_fade_block(infile, offset, start_frame, end_frame):
    def reader_callback(data):
        points = []

        for i in range((len(data) - 4) // 4):
            frame, opacity, opacity2 = struct.unpack("<HBB", data[i*4:i*4+4])
            frame = ctypes.c_short(frame).value
            opacity = ctypes.c_short(opacity).value
            opacity2 = ctypes.c_short(opacity2).value

            opacity = abs(ctypes.c_byte(opacity).value / 100)
            opacity2 = abs(ctypes.c_byte(opacity2).value / 100)

            points.append({
                'frame': frame,
                'opacity': opacity,
                'opacity2': opacity2,
            })

        print(points)

        return points


    def logic_callback(points, i, j, start_frame, end_frame):
        frame_count = end_frame - start_frame

        opacity_diff = points[i+1]['opacity'] - points[i]['opacity']
        opacity_step = opacity_diff / frame_count

        opacity2_diff = points[i+1]['opacity2'] - points[i]['opacity2']
        opacity2_step = opacity2_diff / frame_count

        cur_opacity = points[i]['opacity'] + opacity_step * j
        cur_opacity2 = points[i]['opacity2'] + opacity2_step * j

        return {
            'frame': start_frame + j,
            'opacity': cur_opacity,
            'opacity2': cur_opacity2,
        }


    def point_callback(point):
        return {
            'frame': point['frame'],
            'opacity': point['opacity'],
            'opacity2': point['opacity2'],
        }

    return read_data_block(infile, offset, end_frame, reader_callback, logic_callback, point_callback)


def read_rotation_block(infile, offset, start_frame, end_frame):
    def reader_callback(data):
        points = []

        for i in range((len(data) - 4) // 4):
            frame, rotation = struct.unpack("<HH", data[i*4:i*4+4])
            frame = ctypes.c_short(frame).value
            rotation = ctypes.c_short(rotation).value

            points.append({
                'frame': frame,
                'rotation': rotation,
            })

        return points


    def logic_callback(points, i, j, start_frame, end_frame):
        frame_count = end_frame - start_frame

        rotation_diff = points[i+1]['rotation'] - points[i]['rotation']
        rotation_step = rotation_diff / frame_count

        cur_rotation = points[i]['rotation'] + rotation_step * j

        return {
            'frame': start_frame + j,
            'rotation': cur_rotation,
        }

    return read_data_block(infile, offset, end_frame, reader_callback, logic_callback)
