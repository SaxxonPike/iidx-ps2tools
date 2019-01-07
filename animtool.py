import gc

import base64
import copy
import ctypes
import os
import struct
import sys
import subprocess
import tempfile

from PIL import Image, ImageOps, ImageChops
import imageio

import hexdump
import argparse


def decode_lzss(input_data, decompSize):
    # Based on decompression code from IIDX GOLD CS
    input_data = bytearray(input_data)
    idx = 0

    output = bytearray()

    BUFFER_SIZE = 0x1000
    BUFFER_OFFSET = 0xfee

    buffer = bytearray([0] * BUFFER_SIZE)

    control = 0
    while len(output) < decompSize:
        control >>= 1

        if (control & 0x100) == 0:
            control = input_data[idx] | 0xff00
            idx += 1

        if (control & 1) != 0:
            data = input_data[idx]
            idx += 1

            output.append(data)
            buffer[BUFFER_OFFSET] = data
            BUFFER_OFFSET = (BUFFER_OFFSET + 1) % BUFFER_SIZE

        else:
            t1 = input_data[idx]
            idx += 1

            a3 = input_data[idx]
            idx += 1

            length = (a3 & 0x0f) + 3
            offset = ((a3 & 0xf0) << 4) | t1
#            offset = BUFFER_OFFSET - offset

            #print("%04x %04x | %04x %04x | %08x %08x" % (len(input_data), idx, offset, length, len(output), decompSize))

            while length > 0:
                data = buffer[offset]
                output.append(data)
                buffer[BUFFER_OFFSET] = data

                BUFFER_OFFSET = (BUFFER_OFFSET + 1) % BUFFER_SIZE
                offset = (offset + 1) % BUFFER_SIZE
                length -= 1

    return output


class AnimationPs2:
    def __init__(self, filename, output_folder):
        self.prerendered_frames = {}
        self.rendered_animations = {}

        self.filenames = self.extract_files(filename)
        self.sprite_images = self.extract_sprite_images(self.filenames)
        self.main_sprite = self.generate_main_sprite(self.sprite_images)
        self.sprite_info = self.get_sprite_info(self.filenames[0])
        self.sprite_elements = self.extract_sprite_elements(self.main_sprite, self.sprite_info)
        self.animation_list = self.get_animation_info(self.filenames[0])
        self.output_folder = output_folder

        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)


    def __del__(self):
        self.cleanup()


    def generate_key(self, frame, frame_idx):
        data = struct.pack("<IIIII", frame['anim_id'], frame['anim_type'], frame['anim_format'], frame['w'], frame['h'])

        if frame_idx in frame['position']:
            data += struct.pack("<ii", frame['position'][frame_idx]['x'], frame['position'][frame_idx]['y'])

        if frame_idx in frame['zooms']:
            data += struct.pack("<dd", frame['zooms'][frame_idx]['scale_x'], frame['zooms'][frame_idx]['scale_y'])

        if frame_idx in frame['rotations']:
            data += struct.pack("<d", frame['rotations'][frame_idx]['rotation'])

        if frame_idx in frame['fades']:
            data += struct.pack("<d", frame['fades'][frame_idx]['opacity'])

        return base64.b64encode(data)


    def read_variable_section(self, infile):
        data = []

        while True:
            data.append(infile.read(4))

            if data[-1] == b'\xff\xff\x00\x00':
                break

        return b''.join(data)


    def read_position_block(self, infile, offset, start_frame, end_frame):
        if offset in [0x0000, 0xffff]:
            return {}

        cur_offset = infile.tell()
        infile.seek(offset)
        block_data2 = self.read_variable_section(infile)
        infile.seek(cur_offset)

        print("Position")
        hexdump.hexdump(block_data2)

        points = []
        for i in range((len(block_data2) - 4) // 8):
            frame, x, y, _ = struct.unpack("<HHHH", block_data2[i*8:i*8+8])
            frame = ctypes.c_short(frame).value
            x = ctypes.c_short(x).value
            y = ctypes.c_short(y).value

            if frame < start_frame:
                frame = start_frame
            elif frame > end_frame:
                frame = end_frame

            points.append({
                'frame': frame,
                'x': x,
                'y': y,
            })

        if len(points) == 0:
            return {}

        output = {}
        main_start_frame = points[0]['frame']
        for i in range(len(points) - 1):
            start_frame = points[i]['frame']
            end_frame = points[i+1]['frame']

            if start_frame == end_frame:
                continue

            for j in range(0, end_frame - start_frame):
                cur_x = round(points[i]['x'] + (((points[i+1]['x'] - points[i]['x']) / (end_frame - start_frame)) * j))
                cur_y = round(points[i]['y'] + (((points[i+1]['y'] - points[i]['y']) / (end_frame - start_frame)) * j))

                output[main_start_frame + j] = {
                    'frame': main_start_frame + j,
                    'x': cur_x,
                    'y': cur_y,
                }

            main_start_frame += end_frame - start_frame

        for point in points:
            output[point['frame']] = point

        print(output)

        return output


    def read_zoom_block(self, infile, offset, start_frame, end_frame):
        if offset in [0x0000, 0xffff]:
            return {}

        cur_offset = infile.tell()
        infile.seek(offset)
        block_data2 = self.read_variable_section(infile)
        infile.seek(cur_offset)

        print("Zoom")
        hexdump.hexdump(block_data2)

        points = []
        for i in range((len(block_data2) - 4) // 8):
            frame, scale_x, scale_y, _ = struct.unpack("<HHHH", block_data2[i*8:i*8+8])
            frame = ctypes.c_short(frame).value
            scale_x = ctypes.c_short(scale_x).value
            scale_y = ctypes.c_short(scale_y).value

            if frame < start_frame or frame > end_frame:
                continue

            points.append({
                'frame': frame,
                'scale_x': scale_x,
                'scale_y': scale_y,
            })

        if len(points) == 0:
            return {}

        output = {}
        main_start_frame = points[0]['frame']
        for i in range(len(points) - 1):
            start_frame = points[i]['frame']
            end_frame = points[i+1]['frame']

            if start_frame == end_frame:
                continue

            for j in range(0, end_frame - start_frame):
                cur_scale_x = (points[i]['scale_x'] + (((points[i+1]['scale_x'] - points[i]['scale_x']) / (end_frame - start_frame)) * j)) / 100
                cur_scale_y = (points[i]['scale_y'] + (((points[i+1]['scale_y'] - points[i]['scale_x']) / (end_frame - start_frame)) * j)) / 100

                output[main_start_frame + j] = {
                    'frame': main_start_frame + j,
                    'scale_x': cur_scale_x,
                    'scale_y': cur_scale_y,
                }

            main_start_frame += end_frame - start_frame

        for point in points:
            output[point['frame']] = {
                'frame': point['frame'],
                'scale_x': point['scale_x'] / 100,
                'scale_y': point['scale_y'] / 100,
            }

        #print(output)

        return output


    def read_fade_block(self, infile, offset, start_frame, end_frame):
        if offset in [0x0000, 0xffff]:
            return {}

        cur_offset = infile.tell()
        infile.seek(offset)
        block_data2 = self.read_variable_section(infile)
        infile.seek(cur_offset)

        print("Fade")
        hexdump.hexdump(block_data2)

        points = []

        for i in range((len(block_data2) - 4) // 4):
            frame, opacity, next_opacity = struct.unpack("<HBB", block_data2[i*4:i*4+4])
            frame = ctypes.c_short(frame).value
            opacity = ctypes.c_short(opacity).value
            next_opacity = ctypes.c_short(next_opacity).value

            if frame < start_frame or frame > end_frame:
                continue

            points.append({
                'frame': frame,
                'opacity': opacity,
                'next_opacity': next_opacity,
            })

        if len(points) == 0:
            return {}

        output = {}
        main_start_frame = points[0]['frame']
        for i in range(len(points) - 1):
            start_frame = points[i]['frame']
            end_frame = points[i+1]['frame']

            if start_frame == end_frame:
                continue

            for j in range(0, end_frame - start_frame):
                cur_opacity = (points[i]['opacity'] + (((points[i+1]['opacity'] - points[i]['opacity']) / (end_frame - start_frame)) * j)) / 100

                output[main_start_frame + j] = {
                    'frame': main_start_frame + j,
                    'opacity': cur_opacity,
                }

                #print(main_start_frame, main_start_frame + j, main_start_frame + (end_frame - start_frame), output[main_start_frame + j])

            main_start_frame += end_frame - start_frame

        for point in points:
            output[point['frame']] = {
                'frame': point['frame'],
                'opacity': point['opacity'] / 100
            }

        print(output)

        return output


    def read_rotation_block(self, infile, offset, start_frame, end_frame):
        if offset in [0x0000, 0xffff]:
            return {}

        cur_offset = infile.tell()
        infile.seek(offset)
        block_data2 = self.read_variable_section(infile)
        infile.seek(cur_offset)

        print("Rotation")
        hexdump.hexdump(block_data2)

        points = []

        for i in range((len(block_data2) - 4) // 4):
            frame, rotation = struct.unpack("<HH", block_data2[i*4:i*4+4])
            frame = ctypes.c_short(frame).value
            rotation = ctypes.c_short(rotation).value

            if frame < start_frame or frame > end_frame:
                continue

            points.append({
                'frame': frame,
                'rotation': rotation,
            })

        if len(points) == 0:
            return {}

        output = {}
        main_start_frame = points[0]['frame']
        for i in range(len(points) - 1):
            start_frame = points[i]['frame']
            end_frame = points[i+1]['frame']

            if start_frame == end_frame:
                continue

            for j in range(0, end_frame - start_frame):
                cur_rotation = points[i]['rotation'] + (((points[i+1]['rotation'] - points[i]['rotation']) / (end_frame - start_frame)) * j)

                output[main_start_frame + j] = {
                    'frame': main_start_frame + j,
                    'rotation': cur_rotation,
                }

            main_start_frame += end_frame - start_frame

        for point in points:
            output[point['frame']] = point

        #print(output)

        return output


    def extract_files(self, filename):
        filenames = []

        with open(args.input, "rb") as infile:
            data = infile.read()

            base_filename = os.path.splitext(args.input)[0]

            data_offset, file_count = struct.unpack("<HH", data[0x00:0x04])

            START_OFFSET = data_offset - (file_count + 1) * 8

            for i in range(file_count + 1):
                decomp_len, comp_len = struct.unpack("<II", data[START_OFFSET+(i*0x08):START_OFFSET+((i+1)*0x08)])

                print("Decompressing", i, "%08x %08x" % (decomp_len, comp_len))
                output_data = decode_lzss(data[data_offset:], decomp_len)
                data_offset += comp_len

                filename = tempfile.mkstemp(suffix=".raw")[1]
                with open(filename, "wb") as outfile:
                    outfile.write(output_data)

                filenames.append(filename)

        return filenames

    def extract_sprite_images(self, filenames):
        SPRITE_BPP = 8

        sprite_images = []
        with open(filenames[0], "rb") as infile:
            infile.seek(0x10)

            for filename in filenames[1:]:
                width, height = struct.unpack("<HH", infile.read(4))
                subprocess.call(["./texdecode", filename, filename, str(width), str(height), str(SPRITE_BPP)])

                data = open(filename, "rb").read()
                hexdump.hexdump(data[:0x100])
                sprite_images.append(Image.frombytes('RGBA', (width, height), data))

                os.unlink(filename)

        return sprite_images


    def generate_main_sprite(self, sprite_images):
        widths, heights = zip(*(i.size for i in sprite_images))

        max_width = max(widths)
        total_height = 1024 * len(heights)

        main_sprite = Image.new('RGBA', (max_width, total_height), (0, 0, 0, 0))

        y_offset = 0
        for im in sprite_images:
            main_sprite.paste(im, (0, y_offset), im)
            y_offset += 1024

        return main_sprite


    def extract_sprite_elements(self, main_sprite, sprite_info):
        sprite_elements = []

        for i in range(len(sprite_info)):
            x, y, w, h = sprite_info[i]

            print(i, x, y, w, h, main_sprite.size)

            s = main_sprite.crop((x, y, x + w, y + h))
            sprite_elements.append(s)

        return sprite_elements


    def get_sprite_info(self, filename):
        sprite_info = []

        with open(filename, "rb") as infile:
            _, sheets, animations, sprites, sprite_info_offset, animations_offset = struct.unpack("<HHHHII", infile.read(0x10))

            for i in range(sprites):
                infile.seek(sprite_info_offset + (i * 0x08))
                x, y, w, h = struct.unpack("<HHHH", infile.read(8))
                sprite_info.append((x, y, w, h))

        return sprite_info


    def get_animation_info(self, filename):
        animation_list = []

        with open(filename, "rb") as infile:
            _, sheets, animations, sprites, sprite_info_offset, animations_offset = struct.unpack("<HHHHII", infile.read(0x10))

            for i in range(animations):
                infile.seek(animations_offset + (i * 0x04))
                offset = struct.unpack("<I", infile.read(0x04))[0]

                infile.seek(offset)

                cur_anim_frames = []

                print("File", i)
                while True:
                    block_data = infile.read(0x24)
                    infile.seek(-0x24, 1)

                    print()
                    print("Data")
                    hexdump.hexdump(block_data)

                    anim_type, anim_id, anim_format, _, start_frame, end_frame, _ = struct.unpack("<HHHHHHI", infile.read(0x10))
                    w, h, position_info_offset = struct.unpack("<HHI", infile.read(0x08))
                    zoom_info_offset, fade_info_offset, rotation_info_offset = struct.unpack("<III", infile.read(0x0c))

                    w *= 2
                    h *= 2

                    positions_pre = self.read_position_block(infile, position_info_offset, start_frame, end_frame)
                    zooms = self.read_zoom_block(infile, zoom_info_offset, start_frame, end_frame)
                    fades = self.read_fade_block(infile, fade_info_offset, start_frame, end_frame)
                    rotations = self.read_rotation_block(infile, rotation_info_offset, start_frame, end_frame)

                    def pad_data(data, start_frame, end_frame):
                        output = data

                        keys = sorted(data.keys())
                        if len(keys) > 0:
                            for j in range(0, sorted(output.keys())[0]):
                                output[j] = data[keys[0]]

                            for j in range(output[sorted(output.keys())[-1]]['frame'], end_frame):
                                output[j] = data[keys[-1]]

                        return output

                    positions = pad_data(positions_pre, start_frame, end_frame)
                    zooms = pad_data(zooms, start_frame, end_frame)
                    fades = pad_data(fades, start_frame, end_frame)
                    rotations = pad_data(rotations, start_frame, end_frame)

                    cur_anim_frames.append({
                        'anim_type': anim_type,
                        'anim_id': anim_id,
                        'anim_format': anim_format,
                        'position': positions,
                        'zooms': zooms,
                        'fades': fades,
                        'rotations': rotations,
                        'w': w,
                        'h': h,
                        'start_frame': start_frame,
                        'end_frame': end_frame,
                    })

                    if anim_id == 0xffff:
                        print()
                        break

                    # if anim_id == 124 and i > 24:
                    #     print(i)
                    #     exit(1)

                animation_list.append({
                    'anim_id': i,
                    'frames': cur_anim_frames[::-1],
                })

        return animation_list



    def process_frame(self, frame, frame_idx, frame_type):
        #print(frame['anim_id'], frame_idx, frame_type)

        if frame_idx not in frame['position']:
            return None, None, None, None

        if frame_type in [0, 3]:
            target_sprite = self.sprite_elements[frame['anim_id']].copy()

        elif frame_type in [2]:
            if frame['anim_id'] not in self.rendered_animations:
                self.render_animation(frame['anim_id'])

            frame_key = self.generate_key(frame, frame_idx)

            # TODO: Hack
            if frame_key not in self.prerendered_frames:
                return None, None, None, None
            else:
                target_sprite = Image.open(self.prerendered_frames[frame_key])

        if frame_idx in frame['zooms']:
            new_w = target_sprite.width * frame['zooms'][frame_idx]['scale_x']
            new_h = target_sprite.height * frame['zooms'][frame_idx]['scale_y']

            # print(frame['zooms'][frame_idx])
            # print(new_w, new_h)

            if new_w < 0:
                target_sprite2 = target_sprite.transpose(Image.FLIP_LEFT_RIGHT)
                target_sprite.close()
                del target_sprite
                target_sprite = target_sprite2
                new_w = abs(new_w)

            if new_h < 0:
                target_sprite2 = target_sprite.transpose(Image.FLIP_TOP_BOTTOM)
                target_sprite.close()
                del target_sprite
                target_sprite = target_sprite2
                new_h = abs(new_h)

            new_w = round(new_w)
            new_h = round(new_h)

            if new_w <= 0 or new_h <= 0:
                target_sprite2 = Image.new(target_sprite.mode, target_sprite.size, (0, 0, 0, 0))
            else:
                target_sprite2 = target_sprite.resize((new_w, new_h))

            target_sprite.close()
            del target_sprite
            target_sprite = target_sprite2

        if frame_idx in frame['position']:
            frame_x = frame['position'][frame_idx]['x'] - (target_sprite.size[0] // 2)
            frame_y = frame['position'][frame_idx]['y'] - (target_sprite.size[1] // 2)

            print(frame_idx, frame['anim_id'], frame_x, frame_y, frame['position'][frame_idx])

        if frame['w'] == 0:
            frame_x += target_sprite.size[0]

        if frame['h'] == 0:
            frame_y += target_sprite.size[1]

        if frame_idx in frame['fades']:
            a = Image.new(target_sprite.mode, target_sprite.size, (0, 0, 0, 0))
            target_sprite2 = Image.blend(a, target_sprite, frame['fades'][frame_idx]['opacity'])

            target_sprite.close()
            a.close()
            del a
            del target_sprite

            target_sprite = target_sprite2

        if frame_idx in frame['rotations']:
            old_size = target_sprite.size
            target_sprite2 = target_sprite.rotate(-frame['rotations'][frame_idx]['rotation'], expand=True)

            target_sprite.close()
            del target_sprite
            target_sprite = target_sprite2

            frame_x -= (target_sprite.size[0] - old_size[0]) // 2
            frame_y -= (target_sprite.size[1] - old_size[1]) // 2

        # if frame['anim_format'] == 2:
        #     # Mask?
        #     new_target_sprite = Image.new('RGBA', target_sprite.size)

        #     datas = target_sprite.convert('L').getdata()

        #     newData = []
        #     for item in datas:
        #         newData.append((255, 255, 255, item))

        #     new_target_sprite.putdata(newData)
        #     target_sprite = new_target_sprite
        #     mask = new_target_sprite

        return target_sprite, target_sprite, frame_x, frame_y


    def render_animation(self, animation_id):
        animation_info = None

        for animation in self.animation_list:
            if animation['anim_id'] == animation_id:
                animation_info = animation
                break

        if animation_info is None:
            print("Couldn't find specified animation")
            exit(1)

        print("Animation ID:", animation_info['anim_id'])

        if animation_info['anim_id'] not in self.rendered_animations:
            self.rendered_animations[animation_info['anim_id']] = []
        else:
            return

        # Find metadata frame
        metadata_frame = None
        for frame in animation_info.get('frames', []):
            if frame['anim_type'] == 0xffff:
                metadata_frame = frame
                break

        if metadata_frame is None:
            print("Couldn't find metadata frame")
            exit(1)
            return None

        for i in range(metadata_frame['start_frame'], metadata_frame['end_frame']):
            cur_frame_render = Image.new('RGBA', (metadata_frame['w'], metadata_frame['h']), (0, 0, 0, 0))

            for frame in animation_info.get('frames', []):
                if i < frame['start_frame'] or i >= frame['end_frame']:
                    continue

                frame_idx = i

                frame_key = self.generate_key(frame, frame_idx)

                if frame_key in self.prerendered_frames:
                    continue

                if frame['anim_type'] == 0xffff:
                    # Info about the output render size and number of frames
                    continue

                elif frame['anim_type'] in [0, 2, 3]:
                    sprite, mask, frame_x, frame_y = self.process_frame(frame, frame_idx, frame['anim_type'])

                    if sprite == None and mask == None:
                        continue

                    if frame['anim_format'] == 1:
                        cur_frame_render.paste(Image.new('RGBA', sprite.size, (0, 0, 0, 255)), (frame_x, frame_y), sprite.convert('L'))

                    elif frame['anim_format'] == 2:
                        new_target_sprite = Image.new('RGBA', cur_frame_render.size, (0, 0, 0, 255))
                        new_target_sprite.paste(sprite, (frame_x, frame_y), mask)
                        cur_frame_render = ImageChops.add(cur_frame_render, new_target_sprite)

                    else:
                        cur_frame_render.paste(sprite, (frame_x, frame_y), mask)

                    sprite.close()
                    del sprite

                else:
                    print("Unimplemented animation type")
                    print(animation_id, frame)
                    #exit(1)

            temp_filename = tempfile.NamedTemporaryFile(suffix=".png").name
            cur_frame_render.save(temp_filename)

            frame_key = self.generate_key(frame, frame_idx)
            self.prerendered_frames[frame_key] = temp_filename
            self.rendered_animations[animation['anim_id']].append(temp_filename)

        # if len(self.rendered_animations[animation_id]) > 0:
        #     first_frame = Image.open(self.rendered_animations[animation_id][0])

        #     with imageio.get_writer("output_%d.mp4" % animation_id, mode='I', fps=60) as writer:
        #         for filename in self.rendered_animations[animation_id]:
        #             image = imageio.imread(filename)
        #             writer.append_data(image)

        if len(self.rendered_animations[animation_id]) > 0:
            first_frame = Image.open(self.rendered_animations[animation_id][0])

            if first_frame:
                append_images = [Image.open(x) for x in self.rendered_animations[animation_id][1:]]
                first_frame.save(os.path.join(self.output_folder, "output_%d.gif" % animation_id), save_all=True, append_images=append_images, loop=0xffff, disposal=0, fps=60)

                first_frame.close()

                for x in append_images:
                    x.close()


    def render_all(self):
        self.render_by_id(list(range(len(self.animation_list))))


    def render_by_id(self, ids=[]):
        self.prerendered_frames = {}
        self.rendered_animations = {}

        if isinstance(ids, int):
            ids = [ids]

        for id in ids:
            if id > len(self.animation_list):
                print("Index out of range, skipping...", id)
                continue

            self.render_animation(self.animation_list[id]['anim_id'])


    def cleanup(self):
        for idx in self.prerendered_frames:
            if os.path.exists(self.prerendered_frames[idx]):
                os.unlink(self.prerendered_frames[idx])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', help='Input file')
    parser.add_argument('--output', help='Output folder')
    args = parser.parse_args()

    animparser = AnimationPs2(args.input, args.output)
    animparser.render_all()
    animparser.cleanup()
