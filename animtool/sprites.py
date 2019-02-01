# pylint: disable=missing-docstring

import os
import struct
import tempfile

from PIL import Image

import animtool.ps2textures as ps2textures
import animtool.transforms as transforms


def decode_lzss(input_data, decomp_size):
    # Based on decompression code from IIDX GOLD CS
    input_data = bytearray(input_data)
    idx = 0

    output = bytearray()

    BUFFER_SIZE = 0x1000
    BUFFER_OFFSET = 0xfee

    buffer = bytearray([0] * BUFFER_SIZE)

    control = 0
    while len(output) < decomp_size:
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
            length = (input_data[idx+1] & 0x0f) + 3
            offset = ((input_data[idx+1] & 0xf0) << 4) | input_data[idx]
            idx += 2

            while length > 0:
                data = buffer[offset]
                output.append(data)
                buffer[BUFFER_OFFSET] = data

                BUFFER_OFFSET = (BUFFER_OFFSET + 1) % BUFFER_SIZE
                offset = (offset + 1) % BUFFER_SIZE
                length -= 1

    return output


def extract_files(filename):
    filenames = []

    with open(filename, "rb") as infile:
        data = infile.read()

        data_offset, file_count = struct.unpack("<HH", data[0x00:0x04])

        START_OFFSET = data_offset - (file_count + 1) * 8

        for i in range(file_count + 1):
            decomp_len, comp_len = struct.unpack("<II", data[START_OFFSET+(i*0x08):START_OFFSET+((i+1)*0x08)])

            output_data = decode_lzss(data[data_offset:], decomp_len)
            data_offset += comp_len

            temp_file, filename = tempfile.mkstemp(suffix=".raw")
            os.close(temp_file)

            with open(filename, "wb") as outfile:
                outfile.write(output_data)

            filenames.append(filename)

    return filenames


def extract_sprite_images(filenames):
    SPRITE_BPP = 8

    sprite_images = []
    with open(filenames[0], "rb") as infile:
        infile.seek(0x10)

        # TODO: Maybe make texture decoding and loading threaded? Not much of a speed issue anymore compared to before
        for idx, filename in enumerate(filenames[1:]):
            print("Decoding texture %d..." % idx)
            width, height = struct.unpack("<HH", infile.read(4))
            data = ps2textures.decode_ps2_texture(filename, width, height, SPRITE_BPP)
            data_bytes = bytes(data)
            del data
            sprite_images.append(Image.frombytes('RGBA', (width, height), data_bytes))
            del data_bytes

    return sprite_images


def generate_main_sprite(sprite_images):
    SHEET_HEIGHT = 1024

    widths, heights = zip(*(i.size for i in sprite_images))

    max_width = max(widths)
    total_height = SHEET_HEIGHT * len(heights)

    main_sprite = Image.new('RGBA', (max_width, total_height), (0, 0, 0, 0))

    for idx, image in enumerate(sprite_images):
        main_sprite.paste(image, (0, SHEET_HEIGHT * idx), image)
        # image.save("sprite_%04d.png" % idx)

    # main_sprite.save("main_sprite.png")

    return main_sprite


def extract_sprite_elements(filenames):
    sprite_images = extract_sprite_images(filenames)
    main_sprite = generate_main_sprite(sprite_images)
    sprite_info = get_sprite_info(filenames[0]) # The first file is always the metadata file

    for sprite in sprite_images:
        sprite.close()
        del sprite

    sprite_elements = []
    for idx, (sprite_x, sprite_y, sprite_w, sprite_h) in enumerate(sprite_info):
        crop_region = (
            sprite_x,
            sprite_y,
            sprite_x + sprite_w,
            sprite_y + sprite_h
        )

        sprite_cropped = main_sprite.crop(crop_region)
        sprite_elements.append(sprite_cropped)
        # sprite_elements[-1].save("image_%04d.png" % idx, format="png", compress_level=0)

    main_sprite.close()
    del main_sprite

    return sprite_elements


def get_sprite_info(filename):
    sprite_info = []

    with open(filename, "rb") as infile:
        _, sheets, animations, sprites, sprite_info_offset, animations_offset = struct.unpack("<HHHHII", infile.read(0x10))

        for i in range(sprites):
            infile.seek(sprite_info_offset + (i * 0x08))
            sprite_x, sprite_y, sprite_w, sprite_h = struct.unpack("<HHHH", infile.read(8))
            sprite_info.append((sprite_x, sprite_y, sprite_w, sprite_h))

    return sprite_info


def get_animation_info(filename):
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
                import hexdump
                hexdump.hexdump(block_data)

                anim_type, anim_id, anim_format, opacity, start_frame, end_frame, frame_offset = struct.unpack("<HHHHHHI", infile.read(0x10))
                sprite_x, sprite_y, position_info_offset = struct.unpack("<HHI", infile.read(0x08))
                zoom_info_offset, fade_info_offset, rotation_info_offset = struct.unpack("<III", infile.read(0x0c))

                positions = transforms.read_position_block(infile, position_info_offset, start_frame, end_frame)
                zooms = transforms.read_zoom_block(infile, zoom_info_offset, start_frame, end_frame)
                fades = transforms.read_fade_block(infile, fade_info_offset, start_frame, end_frame)
                rotations = transforms.read_rotation_block(infile, rotation_info_offset, start_frame, end_frame)

                cur_anim_frames.append({
                    'anim_type': anim_type,
                    'anim_id': anim_id,
                    'anim_format': anim_format,
                    'position': positions,
                    'zooms': zooms,
                    'fades': fades,
                    'rotations': rotations,
                    'opacity': opacity / 100 if opacity <= 100 else 1.0,
                    'x': sprite_x,
                    'y': sprite_y,
                    'start_frame': start_frame,
                    'end_frame': end_frame,
                    'frame_offset': frame_offset,
                })

                if anim_id == 0xffff:
                    break

            # Fix end frame since overflow frames are also a thing apparently
            # Find metadata frame
            max_end_frame = 0
            metadata_frame = None
            for idx, frame in enumerate(cur_anim_frames):
                if frame['end_frame'] > max_end_frame:
                    max_end_frame = frame['end_frame']

                if frame['anim_type'] == 0xffff:
                    metadata_frame = idx

            if metadata_frame is None:
                print("Couldn't find metadata frame")
                exit(1)

            cur_anim_frames[idx]['end_frame'] = max_end_frame

            animation_list.append({
                'anim_id': i,
                'frames': cur_anim_frames[::-1],
            })

    return animation_list
