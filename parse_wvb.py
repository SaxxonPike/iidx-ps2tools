import argparse
import os
import struct
import sys
import subprocess

import pydub


def percentage_to_db(percentage):
    if percentage == 0:
        return 0

    import math
    return 20 * math.log10(percentage / 100)


def find_num_samples(infile, offset):
    cur_offset = infile.tell()
    infile.seek(offset)

    # TODO: This could be a potential source of problems
    # vgmstream also uses these signatures to detect the end frame, so it should be ok I think?
    filesize = 0
    while infile.read(16) not in [b'\x00\x07' + b'\x77' * 14, b'\x00\x07' + b'\x00' * 14]:
        filesize += 16

    infile.seek(cur_offset)

    return filesize


def parse_wvb_old(infile, output_folder):
    archive_size, section_size, section2_relative_offset = struct.unpack("<III", infile.read(12))
    section2_offset = archive_size - section2_relative_offset

    infile.seek(0x20)

    file_id = 0

    while infile.tell() < 0x4000:
        entry_id, _, _, volume, pan, entry_type, sample_rate1, sample_rate2, offset1, offset2, filesize, _ = struct.unpack("<HHBBBBIIIIII", infile.read(0x20))

        cur_offset = infile.tell()

        files = []

        if entry_type == 0:
            continue

        elif entry_type == 2:
            offset1 -= 0xf020
            files.append([offset1, sample_rate1, find_num_samples(infile, offset1)])

        elif entry_type == 4:
            files.append([offset1 - 0xf020, sample_rate1, offset2 - offset1])

        elif entry_type == 3:
            files.append([section2_offset + offset1, sample_rate1, filesize])

        else:
            print("Unknown entry type:", entry_type, "%02x" % (infile.tell() - 0x20))
            exit(1)


        for offset, sample_rate, size in files:
            output_filename = os.path.join(output_folder, "%04d.pcm" % entry_id)

            print("Extracting", output_filename)

            with open(output_filename, "wb") as outfile:
                outfile.write(struct.pack(">IHHB", size, 0, sample_rate, 1))
                outfile.write(bytearray([0] * 0x7f7))

                infile.seek(offset)
                outfile.write(infile.read(size))

            wav_output_filename = output_filename.replace(".pcm", ".wav")
            subprocess.call('test.exe -o "%s" "%s"' % (wav_output_filename, output_filename))
            os.unlink(output_filename)

            wav = pydub.AudioSegment.from_file(wav_output_filename)
            wav = wav.pan((pan - (128 / 2)) / (128 / 2))
            wav += percentage_to_db((volume / 127) * 100 * 0.75)
            wav.export(wav_output_filename, format="wav")

        infile.seek(cur_offset)


def parse_wvb_new(infile, output_folder):
    header, keysound_table_offset = struct.unpack("<II", infile.read(8))
    infile.seek(0x10, 0)

    keysound_entries = []
    for i in range(0, (0x8000 - 0x10) // 0x10):
        unk1, unk2, unk3, pan_l, pan_r, file_id, volume = struct.unpack("<HHIBBHI", infile.read(16))

        if unk1 == 0:
            continue

        keysound_entries.append({
            'unk1': unk1,
            'unk2': unk2,
            'unk3': unk3,
            'pan_l': pan_l,
            'pan_r': pan_r,
            'file_id': file_id,
            'volume': volume,
            'entry_id': i,
        })

    file_count = struct.unpack("<I", infile.read(4))[0]
    infile.seek(0x0c, 1)

    file_entries = []
    for i in range(0, file_count):
        offset, filesize, unk1, unk2, unk3 = struct.unpack("<IIHHI", infile.read(16))

        file_entries.append({
            'file_id': i,
            'offset': offset,
            'filesize': filesize,
            'unk1': unk1, # Does this relate to the sample rate?
            'unk2': unk2,
            'unk3': unk3,
        })


    for entry in keysound_entries:
        entry_id = entry['entry_id']
        sample_rate = 44100 #entry['sample_rate']
        size = file_entries[entry['file_id']]['filesize']
        offset = file_entries[entry['file_id']]['offset']
        volume = entry['volume']
        pan = 64

        output_filename = os.path.join(output_folder, "%04d.pcm" % entry_id)

        print("Extracting", output_filename)

        with open(output_filename, "wb") as outfile:
            outfile.write(struct.pack(">IHHB", size, 0, sample_rate, 1))
            outfile.write(bytearray([0] * 0x807))

            infile.seek(offset)
            outfile.write(infile.read(size))

        wav_output_filename = output_filename.replace(".pcm", ".wav")
        subprocess.call('test.exe -o "%s" "%s"' % (wav_output_filename, output_filename))
        os.unlink(output_filename)

        wav = pydub.AudioSegment.from_file(wav_output_filename)
        wav = wav.pan((pan - (128 / 2)) / (128 / 2))
        wav += percentage_to_db((volume / 127) * 100 * 0.75)
        wav.export(wav_output_filename, format="wav")


def parse_wvb(filename, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    with open(filename, "rb") as infile:
        header = struct.unpack("<I", infile.read(4))[0]

        infile.seek(0, 2)
        filelen = infile.tell()
        infile.seek(0, 0)

        if header == filelen:
            parse_wvb_old(infile, output_folder)

        else:
            parse_wvb_new(infile, output_folder)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', help='Input .wvb file', required=True)
    parser.add_argument('--output', help='Output folder', required=True)
    args = parser.parse_args()

    parse_wvb(args.input, args.output)
