import argparse
import os
import struct
import sys
import subprocess
import queue
import threading

import pydub
import common

def convert_vgmstream(input_filename, output_filename, output_format=None, output_frame_rate=None, output_sample_width=None, output_bitrate=None):
    subprocess.call('vgmstream_cli.exe -q -o "%s" "%s"' % (output_filename, input_filename))

    if output_format != None:
        wav = pydub.AudioSegment.from_file(output_filename)
        wav_output_filename = output_filename.replace(".wav", "." + output_format)

        if output_frame_rate:
            wav = wav.set_frame_rate(output_frame_rate)

        if output_sample_width:
            wav = wav.set_sample_width(output_sample_width // 8)

        if output_bitrate:
            wav.export(wav_output_filename, format=output_format, bitrate=output_bitrate)

        else:
            wav.export(wav_output_filename, format=output_format)

        os.unlink(output_filename)


def percentage_to_db(percentage):
    if percentage == 0:
        return 0

    import math
    return 20 * math.log10(percentage / 100)


def find_num_samples(infile, offset):
    cur_offset = infile.tell()
    infile.seek(0, 2)
    filelen = infile.tell()
    infile.seek(offset + 16)

    # TODO: This could be a potential source of problems
    # vgmstream also uses these signatures to detect the end frame, so it should be ok I think?
    filesize = 0
    while infile.tell() < filelen and infile.read(16) not in [b'\x00\x07' + b'\x77' * 14, b'\x00\x07' + b'\x00' * 14, b'\00' * 16]:
        filesize += 16

    infile.seek(cur_offset)

    return filesize


def parse_wvb_old(infile, output_folder, num_threads, output_format="wav", output_frame_rate=44100, output_sample_width=16, output_bitrate=None):
    archive_size, section_size, section2_relative_offset = struct.unpack("<III", infile.read(12))
    section2_offset = archive_size - section2_relative_offset

    infile.seek(0x20)

    file_id = 0
    files = []

    while infile.tell() < 0x4000:
        entry_id, _, _, volume, pan, entry_type, frame_rate1, frame_rate2, offset1, offset2, filesize, _ = struct.unpack("<HHBBBBIIIIII", infile.read(0x20))

        cur_offset = infile.tell()

        entry_type &= 0x0f

        if entry_type == 0:
            continue

        elif entry_type == 2:
            offset1 -= 0xf020
            files.append([entry_id, offset1, frame_rate1, find_num_samples(infile, offset1), volume, pan])

        elif entry_type == 4:
            files.append([entry_id, offset1 - 0xf020, frame_rate1, offset2 - offset1, volume, pan])

        elif entry_type == 3:
            files.append([entry_id, section2_offset + offset1, frame_rate1, filesize, volume, pan])

        else:
            print("Unknown entry type:", entry_type, "%02x" % (infile.tell() - 0x20), output_folder)
            exit(1)

        infile.seek(cur_offset)

    def thread_worker():
        while True:
            item = queue_data.get()

            if item is None:
                break

            output_filename, offset, frame_rate, size, volume, pan = item

            print("Extracting", output_filename)

            wav_output_filename = output_filename.replace(".pcm", ".wav")
            convert_vgmstream(output_filename, wav_output_filename)

            wav = pydub.AudioSegment.from_file(wav_output_filename)

            if output_frame_rate:
                wav = wav.set_frame_rate(output_frame_rate)

            if output_sample_width:
                wav = wav.set_sample_width(output_sample_width // 8)

            wav = wav.pan((pan - (128 / 2)) / (128 / 2))
            wav += percentage_to_db((volume / 127) * 100 * 0.75)

            wav_output_filename = output_filename.replace(".pcm", "." + output_format)

            if output_bitrate:
                wav.export(wav_output_filename, format=output_format, bitrate=output_bitrate)

            else:
                wav.export(wav_output_filename, format=output_format)


            queue_data.task_done()

    queue_data = queue.Queue()
    for entry_id, offset, frame_rate, size, volume, pan in files:
        output_filename = os.path.join(output_folder, "%04d.pcm" % entry_id)

        with open(output_filename, "wb") as outfile:
            outfile.write(struct.pack(">IHHB", size, 0, frame_rate, 1))
            outfile.write(bytearray([0] * 0x7f7))

            infile.seek(offset)
            outfile.write(infile.read(size))

        queue_data.put((output_filename, offset, frame_rate, size, volume, pan))

    common.process_queue(queue_data, thread_worker, num_threads)

    for entry_id, _, _, _, _, _ in files:
        remove_ext = ['pcm']

        if output_format != "wav":
            remove_ext.append("wav")

        for ext in remove_ext:
            output_filename = os.path.join(output_folder, "%04d.%s" % (entry_id, ext))

            if os.path.exists(output_filename):
                os.unlink(output_filename)


def parse_wvb_new(infile, output_folder, num_threads, output_format="wav", output_frame_rate=44100, output_sample_width=16, output_bitrate=None):
    header, keysound_table_offset = struct.unpack("<II", infile.read(8))
    infile.seek(0x10, 0)

    keysound_entries = []
    for i in range(0, (0x8000 - 0x10) // 0x10):
        unk1, unk2, duration_ms, pan, volume, file_id, _ = struct.unpack("<HHIBBHI", infile.read(16))

        if unk1 == 0:
            continue

        keysound_entries.append({
            'duration_ms': duration_ms,
            'pan': pan,
            'file_id': file_id,
            'volume': volume,
            'entry_id': i + 1,
            'mix': [2, 1][(unk2 >> 8) - 1]
        })

    file_count, _, is_encrypted = struct.unpack("<III", infile.read(12))
    infile.seek(0x04, 1)

    file_entries = []
    for i in range(0, file_count):
        offset, filesize, unk1, unk2, unk3 = struct.unpack("<IIHHI", infile.read(16))

        file_entries.append({
            'file_id': i,
            'offset': offset,
            'filesize': filesize,
            'unk1': unk1, # Does one of these relate to the sample rate somehow?
            'unk2': unk2 >> 8,
            'unk2o': unk2,
            'unk3': unk3,
        })

    data_offset = infile.tell()

    files = []
    for entry in keysound_entries:
        entry_id = entry['entry_id']
        size = file_entries[entry['file_id']]['filesize']
        offset = data_offset + file_entries[entry['file_id']]['offset']
        volume = entry['volume']
        pan = entry['pan']
        frame_rate = 44100
        channels = 1

        # Thanks Konami
        frame_rates = {
            0x3e: 44100,
            0x3f: 42000,
            0x40: 40000,
            0x41: 37000,
            0x42: 36000,
            0x43: 34000,
            0x44: 32000,
            0x45: 30000,
            0x46: 28000,
            0x47: 26000,
            0x48: 24000,
            0x4a: 22050,
            0x4c: 20000,
            0x4d: 18000,
            0x50: 16000,
            # 0x51: 15000,
            # 0x52: 14000,
            # 0x53: 13000,
            0x54: 12000,
        }

        print(entry['file_id'], frame_rates[file_entries[entry['file_id']]['unk2']])

        if file_entries[entry['file_id']]['unk2'] in frame_rates:
            frame_rate = frame_rates[file_entries[entry['file_id']]['unk2']]

        else:
            print("Unknown sample rate %04x" % file_entries[entry['file_id']]['unk2o'], output_folder)
            exit(1)

        files.append((entry_id, offset, frame_rate, size, volume, pan))

    def thread_worker():
        while True:
            item = queue_data.get()

            if item is None:
                break

            output_filename, offset, frame_rate, size, volume, pan = item

            print("Extracting", output_filename)

            wav_output_filename = output_filename.replace(".pcm", ".wav")
            convert_vgmstream(output_filename, wav_output_filename)
            wav = pydub.AudioSegment.from_file(wav_output_filename)

            if output_frame_rate:
                wav = wav.set_frame_rate(output_frame_rate)

            if output_sample_width:
                wav = wav.set_sample_width(output_sample_width // 8)

            if entry['mix'] == 1:
                wav = wav.set_channels(2).pan(((pan - (128 / 2)) / (128 / 2)))
                wav += percentage_to_db((volume / 64) * 100 * 0.75)

            else:
                wav += percentage_to_db((volume / 127) * 100 * 0.75)

            wav_output_filename = wav_output_filename.replace(".wav", "." + output_format)

            if output_bitrate:
                wav.export(wav_output_filename, format=output_format, bitrate=output_bitrate)

            else:
                wav.export(wav_output_filename, format=output_format)

            queue_data.task_done()

    queue_data = queue.Queue()
    for entry_id, offset, frame_rate, size, volume, pan in files:
        output_filename = os.path.join(output_folder, "%04d.pcm" % entry_id)

        with open(output_filename, "wb") as outfile:
            outfile.write(struct.pack("<IIII", 0x08640001, 0, 0x800, size))
            outfile.write(struct.pack("<IIII", 0, 0, frame_rate, channels))
            outfile.write(struct.pack("<IIII", is_encrypted, 16, 0, 0))
            outfile.write(bytearray([0] * 0x7d0))

            infile.seek(offset)
            outfile.write(infile.read(size))

        queue_data.put((output_filename, offset, frame_rate, size, volume, pan))

    common.process_queue(queue_data, thread_worker, num_threads)

    for entry_id, _, _, _, _, _ in files:
        remove_ext = ['pcm']

        if output_format != "wav":
            remove_ext.append("wav")

        for ext in remove_ext:
            output_filename = os.path.join(output_folder, "%04d.%s" % (entry_id, ext))

            if os.path.exists(output_filename):
                os.unlink(output_filename)


def parse_wvb(filename, output_folder, threads=4, output_format="wav", output_frame_rate=44100, output_sample_width=16, output_bitrate=None):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    print("Processing", filename)

    with open(filename, "rb") as infile:
        header = struct.unpack("<I", infile.read(4))[0]

        infile.seek(0, 2)
        filelen = infile.tell()
        infile.seek(0, 0)

        if header == filelen:
            parse_wvb_old(infile, output_folder, threads, output_format, output_frame_rate, output_sample_width, output_bitrate)

        else:
            parse_wvb_new(infile, output_folder, threads, output_format, output_frame_rate, output_sample_width, output_bitrate)


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', help='Input .wvb file', required=True)
    parser.add_argument('--output', help='Output folder', required=True)
    parser.add_argument('--threads', help='Number of threads to use during extraction', default=4, type=int)
    parser.add_argument('--output-format', help='Output format', default="wav")
    parser.add_argument('--output-frame-rate', help='Output sample rate', default=None, type=int)
    parser.add_argument('--output-sample-width', help='Output sample width', default=None, type=int)
    parser.add_argument('--output-bitrate', help='Output bitrate (ffmpeg format)', default=None)
    args = parser.parse_args(args)

    parse_wvb(args.input, args.output, args.threads, args.output_format, args.output_frame_rate, args.output_sample_width, args.output_bitrate)


if __name__ == "__main__":
    main(sys.argv[1:])