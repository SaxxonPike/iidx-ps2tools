import argparse
import math
import os
import shutil
import struct
import sys
import subprocess
import queue
import tempfile
import threading

import pydub
import common

def convert_vgmstream(input_filename, output_filename, output_format=None, output_frame_rate=None, output_sample_width=None, output_bitrate=None, volume=100, fix_samples=False):
    original_samples = None
    temp_file = input_filename

    with open(input_filename, "rb") as infile:
        header = infile.read(4)
        if header == b'\x01\x00\x64\x08':
            infile.seek(0x28)
            internal_volume = struct.unpack("<I", infile.read(4))[0]

        else:
            infile.seek(0x05, 0)
            internal_volume = struct.unpack("<B", infile.read(1))[0]

            if fix_samples:
                infile.seek(0, 0)
                original_samples = struct.unpack(">I", infile.read(4))[0]

                temp_id, temp_file = tempfile.mkstemp(suffix=".pcm")
                os.close(temp_id)

                shutil.copyfile(input_filename, temp_file)

    if fix_samples and original_samples:
        with open(temp_file, "rb+") as infile:
            samples = find_num_samples(infile, 0x800)
            infile.seek(0, 0)
            infile.write(struct.pack(">I", samples))

    subprocess.call('vgmstream_cli.exe -q -o "%s" "%s"' % (output_filename, temp_file))

    if fix_samples and original_samples:
        os.unlink(temp_file)

    if output_format != None:
        wav = pydub.AudioSegment.from_file(output_filename)
        wav_output_filename = output_filename.replace(".wav", "." + output_format)

        if output_frame_rate:
            wav = wav.set_frame_rate(output_frame_rate)

        if output_sample_width:
            wav = wav.set_sample_width(output_sample_width // 8)

        if volume != 100:
            wav += percentage_to_db(volume)

        if internal_volume != 100:
            wav += percentage_to_db(internal_volume)

        if output_bitrate:
            wav.export(wav_output_filename, format=output_format, bitrate=output_bitrate)

        else:
            wav.export(wav_output_filename, format=output_format)

        os.unlink(output_filename)


def percentage_to_db(percentage):
    if percentage == 0:
        return 0

    return 20 * math.log10(percentage / 100)


def find_num_samples(infile, offset):
    cur_offset = infile.tell()
    infile.seek(0, 2)
    filelen = infile.tell()
    infile.seek(offset + 16)

    # TODO: This could be a potential source of problems
    # vgmstream also uses these signatures to detect the end frame, so it should be ok I think?
    filesize = 32
    while infile.tell() < filelen and infile.read(16) not in [b'\x00\x01' + b'\x77' * 14, b'\x00\x07' + b'\x77' * 14, b'\x00\x07' + b'\x00' * 14, b'\00' * 16]:
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

        entry_id -= 1

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
            outfile.write(struct.pack(">IHHB", size, 0x64, frame_rate, 1))
            outfile.write(bytearray([0] * 0x7f7))

            infile.seek(offset)
            outfile.write(infile.read(size))

        queue_data.put((output_filename, offset, frame_rate, size, volume, pan))

    common.process_queue(queue_data, thread_worker, num_threads)

    # Create blank wavs to fill in empty spots
    entry_ids = [x[0] for x in files]

    for i in range(max(entry_ids)):
        if i not in entry_ids:
            print("Creating", i)

            output_filename = os.path.join(output_folder, "%04d.%s" % (i, output_format))

            wav = pydub.AudioSegment.silent(0).set_frame_rate(44100)

            if output_bitrate:
                wav.export(output_filename, format=output_format, bitrate=output_bitrate)

            else:
                wav.export(output_filename, format=output_format)

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
        unk1, unk2, duration_ms, pan, volume, file_id, volume2 = struct.unpack("<HHIBBHI", infile.read(16))

        if unk1 == 0:
            continue

        keysound_entries.append({
            'duration_ms': duration_ms,
            'pan': pan,
            'file_id': file_id,
            'volume': volume,
            'volume2': volume2,
            'entry_id': i + 1,
            'mix': [1, 2][(unk2 >> 8) - 1]
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
            'unk1': unk1,
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
        volume2 = entry['volume2']
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

        channels = entry['mix']

        if file_entries[entry['file_id']]['unk2'] in frame_rates:
            frame_rate = frame_rates[file_entries[entry['file_id']]['unk2']]

        else:
            print("Unknown sample rate %04x" % file_entries[entry['file_id']]['unk2o'], output_folder)
            exit(1)

        files.append((entry, entry_id, offset, frame_rate, size, volume, volume2, pan, channels, entry['duration_ms']))

    def get_tagged(input, tag):
        return os.path.splitext(input)[0] + tag + os.path.splitext(input)[1]

    def thread_worker():
        while True:
            item = queue_data.get()

            if item is None:
                break

            entry, output_filename, offset, frame_rate, size, volume, volume2, pan, channels, duration = item

            print("Extracting", output_filename, channels)

            if channels == 2:
                wav_output_filename = output_filename.replace(".pcm", ".wav")

                convert_vgmstream(get_tagged(output_filename, 'l'), get_tagged(wav_output_filename, 'l'))
                l_wav = pydub.AudioSegment.from_file(get_tagged(wav_output_filename, 'l'))

                convert_vgmstream(get_tagged(output_filename, 'r'), get_tagged(wav_output_filename, 'r'))
                r_wav = pydub.AudioSegment.from_file(get_tagged(wav_output_filename, 'r'))

                wav = pydub.AudioSegment.from_mono_audiosegments(l_wav, r_wav)

                os.unlink(get_tagged(wav_output_filename, 'l'))
                os.unlink(get_tagged(wav_output_filename, 'r'))

            else:
                wav_output_filename = output_filename.replace(".pcm", ".wav")
                convert_vgmstream(output_filename, wav_output_filename)
                wav = pydub.AudioSegment.from_file(wav_output_filename)

            if output_frame_rate:
                wav = wav.set_frame_rate(output_frame_rate)

            if output_sample_width:
                wav = wav.set_sample_width(output_sample_width // 8)

            if channels == 2:
                if volume != 127:
                    wav += percentage_to_db((volume / 127) * 100)

            else:
                wav = wav.pan(((pan - (128 / 2)) / (128 / 2)))

                if volume != 64:
                    wav += percentage_to_db((volume / 64) * 100)

            if volume2 != 127:
                wav += percentage_to_db((volume2 / 127) * 100)

            wav_output_filename = wav_output_filename.replace(".wav", "." + output_format)

            if output_bitrate:
                wav.export(wav_output_filename, format=output_format, bitrate=output_bitrate)

            else:
                wav.export(wav_output_filename, format=output_format)

            queue_data.task_done()

    queue_data = queue.Queue()
    for entry, entry_id, offset, frame_rate, size, volume, volume2, pan, channels, duration in files:
        output_filename = os.path.join(output_folder, "%04d.pcm" % entry_id)

        duration /= 1000
        samples_by_duration = math.ceil(((duration + 0.1) * frame_rate) * 1 * 0x10 / 28)

        # TODO: Calculate number of samples by frame rate
        if channels == 2:
            infile.seek(offset)

            for c in ['l', 'r']:
                with open(get_tagged(output_filename, c), "wb") as outfile:
                    outfile.write(struct.pack("<IIII", 0x08640001, 0, 0x800, samples_by_duration))
                    outfile.write(struct.pack("<IIII", 0, 0, frame_rate, 1))
                    outfile.write(struct.pack("<IIII", is_encrypted, 16, 0, 0))
                    outfile.write(bytearray([0] * 0x7d0))

                    outfile.write(infile.read(size))
                    outfile.write(bytearray([0] * 0x10))
        else:
            with open(output_filename, "wb") as outfile:
                outfile.write(struct.pack("<IIII", 0x08640001, 0, 0x800, samples_by_duration))
                outfile.write(struct.pack("<IIII", 0, 0, frame_rate, 1))
                outfile.write(struct.pack("<IIII", is_encrypted, 16, 0, 0))
                outfile.write(bytearray([0] * 0x7d0))

                infile.seek(offset)
                outfile.write(infile.read(size))
                outfile.write(bytearray([0] * 0x10))

        queue_data.put((entry, output_filename, offset, frame_rate, size, volume, volume2, pan, channels, duration))

    common.process_queue(queue_data, thread_worker, num_threads)

    for _, entry_id, _, _, _, _, _, _, _, _ in files:
        remove_ext = ['pcm']

        if output_format != "wav":
            remove_ext.append("wav")

        for ext in remove_ext:
            output_filename = os.path.join(output_folder, "%04d.%s" % (entry_id, ext))

            # if os.path.exists(output_filename):
            #     os.unlink(output_filename)


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