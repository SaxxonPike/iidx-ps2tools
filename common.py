import json
import os
import queue
import threading

import blowfish

import ps2overlay

from animtool.animation_ps2 import AnimationPs2
import iidxtool
import parse_wvb

DIFFICULTY_MAPPING = {
    0: 'SP HYPER',
    1: 'DP HYPER',
    2: 'SP ANOTHER',
    3: 'DP ANOTHER',
    4: 'SP NORMAL',
    5: 'DP NORMAL',
    6: 'SP BEGINNER',
    7: 'DP BEGINNER',
    8: 'SP BLACK',
    9: 'DP BLACK',
}

def process_queue(queue_data, thread_worker, num_threads):
    if queue_data.qsize() == 0:
        return

    threads = []

    for _ in range(num_threads):
        thread = threading.Thread(target=thread_worker)
        thread.start()
        threads.append(thread)

    queue_data.join()

    for _ in range(num_threads):
        queue_data.put(None)

    for thread in threads:
        thread.join()


def decode_lz(input_data):
    # Based on decompression code from IIDX GOLD CS
    input_data = bytearray(input_data)
    idx = 0

    output = bytearray()

    control = 0
    while True:
        control >>= 1

        if (control & 0x100) == 0:
            control = input_data[idx] | 0xff00
            idx += 1

        data = input_data[idx]
        idx += 1

        if (control & 1) == 0:
            output.append(data)
            continue

        length = None
        if (data & 0x80) == 0:
            distance = ((data & 0x03) << 8) | input_data[idx]
            length = (data >> 2) + 2
            idx += 1

        elif (data & 0x40) == 0:
            distance = (data & 0x0f) + 1
            length = (data >> 4) - 7

        if length is not None:
            start_offset = len(output)
            idx2 = 0

            while idx2 <= length:
                output.append(output[(start_offset - distance) + idx2])
                idx2 += 1

            continue

        if data == 0xff:
            break

        length = data - 0xb9
        while length >= 0:
            output.append(input_data[idx])
            idx += 1
            length -= 1

    return output


def decrypt_blowfish(data, key):
    if len(data) % 8 == 0:
        data += bytearray([0] * 8)

    cipher = blowfish.Cipher(key.encode('ascii'), byte_order="little")
    return bytearray(b"".join(cipher.decrypt_cbc_cts(data, bytearray([0] * 8))))


def get_sanitized_filename(filename, invalid_chars='<>:;\"\\/|?*'):
    if not filename:
        return filename

    for c in invalid_chars:
        filename = filename.replace(c, "_")

    return filename


def read_string(infile, offset):
    cur_offset = infile.tell()

    infile.seek(offset)

    string = []
    while True:
        c = infile.read(1)

        if c == b'\0':
            break

        string.append(c)

    infile.seek(cur_offset)

    return b"".join(string).decode('euc-jp')


def extract_file(filename, entry, output_filename):
    if os.path.exists(output_filename):
        base_filename, ext = os.path.splitext(output_filename)
        output_filename = "%s [%04x]%s" % (base_filename, entry['file_id'], ext)

    print("Extracting", output_filename)

    with open(filename, "rb") as infile:
        infile.seek(entry['offset'])
        data = infile.read(entry['size'])

        if entry.get('encryption', None) is not None:
            data = decrypt_blowfish(data, entry['encryption'])

        if entry.get('compression', None) is not None:
            data = entry['compression'](data)

        with open(output_filename, "wb") as outfile:
            outfile.write(data)


def extract_files(file_entries, output_folder, raw_mode, base_file_id=0):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for entry in file_entries[::]:
        if raw_mode:
            entry['references'] = []

        if not entry['references']:
            entry['references'].append({
                'filename': "file_%04d.bin" % (entry['file_id'] + base_file_id),
            })

        for reference in entry['references']:
            if 'title' in reference and not raw_mode:
                output_song_folder = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])))

                if not os.path.exists(output_song_folder):
                    os.makedirs(output_song_folder)

            else:
                output_song_folder = output_folder

            output_filename = os.path.join(output_song_folder, get_sanitized_filename(reference['filename']))
            extract_file(entry['filename'], entry, output_filename)


def extract_overlays(file_entries, output_folder, overlay_exe_offsets):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for entry in file_entries[::]:
        if not entry['references']:
            entry['references'].append({
                'filename': "file_%04d.bin" % (entry['file_id']),
            })

        for reference in entry['references']:
            if 'title' not in reference or 'song_id' not in reference:
                continue

            input_filename = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])), get_sanitized_filename(reference['filename']))

            if not os.path.exists(input_filename):
                continue

            if entry.get('overlays', None) is not None:
                ifs_filenames = []

                for overlay_idx in entry['overlays']['indexes']:
                    ifs_filename = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])), get_sanitized_filename(reference['filename']))
                    output_filename = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])), get_sanitized_filename("%s [%04x]" % (reference['title'], overlay_idx)))
                    ps2overlay.extract_overlay(entry['overlays']['exe'], ifs_filename, entry['overlays']['palette'], overlay_idx, output_filename, overlay_exe_offsets)

                    ifs_filenames.append(ifs_filename)

                for ifs_filename in ifs_filenames:
                    ps2overlay.clear_cache(ifs_filename)

            if entry.get('overlays_new', None) is not None:
                animation_id = []

                for overlay in entry['overlays_new']:
                    animation_id.append(overlay['animation_id'])

                ifs_filename = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])), get_sanitized_filename(reference['filename']))
                output_filename = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])), get_sanitized_filename("%s [%04x]" % (reference['title'], overlay['overlay_idx'])))

                animparser = AnimationPs2(ifs_filename, 8, False)
                animparser.render(animation_id, output_filename, False)


def extract_songs(file_entries, output_folder, chart_format, song_metadata):
    # Extract audio and charts for songs
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    charts_by_song = {}

    def thread_worker():
        while True:
            item = queue_data.get()

            if item is None:
                break

            reference = item

            if 'title' in reference:
                output_song_folder = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])))

                if not os.path.exists(output_song_folder):
                    os.makedirs(output_song_folder)

            else:
                output_song_folder = output_folder

            output_filename = os.path.join(output_song_folder, get_sanitized_filename(reference['filename']))
            base_filename = os.path.splitext(os.path.basename(output_filename))[0]

            if output_filename.endswith(".wvb"):
                # Wavebank/keysound file
                input_filename = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])), get_sanitized_filename(reference['filename']))

                t = "%s" % base_filename
                if not t.strip():
                    t = get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id']))

                output_song_folder = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])), t)

                parse_wvb.parse_wvb(input_filename, output_song_folder)

            elif output_filename.endswith(".pcm"):
                # PCM BGM file
                input_filename = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])), get_sanitized_filename(reference['filename']))

                t = "%s" % base_filename
                if not t.strip():
                    t = get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id']))

                output_song_folder = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])), t)
                output_filename = os.path.join(output_song_folder, "0001.wav")

                parse_wvb.convert_vgmstream(input_filename, output_filename)

            elif output_filename.endswith(".ply"):
                # Chart file
                # This is a lazy way to do this since I still haven't 100% mapped the difficulties at the time of writing.
                # A future TODO: Refactor this code
                if reference['song_id'] not in charts_by_song:
                    charts_by_song[reference['song_id']] = {
                        'title': reference['title'],
                        'charts': {
                            'input_sp_beginner': None,
                            'input_sp_normal': None,
                            'input_sp_hyper': None,
                            'input_sp_another': None,
                            'input_sp_black': None,
                            'input_dp_beginner': None,
                            'input_dp_normal': None,
                            'input_dp_hyper': None,
                            'input_dp_another': None,
                            'input_dp_black': None,
                        },
                        'package': song_metadata[reference['song_id']] if reference['song_id'] in song_metadata else None,
                    }

                for part in ['sp', 'dp']:
                    for difficulty in ['beginner', 'normal', 'hyper', 'another']:
                        if "[%s %s]" % (part.upper(), difficulty.upper()) in output_filename:
                            charts_by_song[reference['song_id']]['charts']['input_%s_%s' % (part, difficulty)] = output_filename

            queue_data.task_done()

    queue_data = queue.Queue()
    used_references = []
    for entry in file_entries[::]:
        for reference in entry['references']:
            if 'title' not in reference:
                continue

            if reference['filename'].endswith(".pcm"):
                continue

            if reference in used_references:
                continue

            used_references.append(reference)

            queue_data.put(reference)

            # Because creating the folders in the threads causes issues when the same song gets processed at the same time...
            output_song_folder = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])))
            output_filename = os.path.join(output_song_folder, get_sanitized_filename(reference['filename']))
            base_filename = os.path.splitext(os.path.basename(output_filename))[0]

            if output_filename.endswith(".wvb") or output_filename.endswith(".pcm"):
                # Wavebank/keysound file
                input_filename = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])), get_sanitized_filename(reference['filename']))

                t = "%s" % base_filename
                if not t.strip():
                    t = get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id']))

                output_song_folder = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (reference['title'], reference['song_id'])), t)

                if not os.path.exists(output_song_folder):
                    os.makedirs(output_song_folder)

    process_queue(queue_data, thread_worker, 4)

    queue_data = queue.Queue()
    used_references = []
    for entry in file_entries[::]:
        for reference in entry['references']:
            if 'title' not in reference:
                continue

            if not reference['filename'].endswith(".pcm"):
                continue

            if reference in used_references:
                continue

            queue_data.put(reference)

    process_queue(queue_data, thread_worker, 4)

    for k in charts_by_song:
        song = charts_by_song[k]

        output_filename = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (song['title'], k)), get_sanitized_filename("%s.json" % song['title']))
        metadata_filename = os.path.join(output_folder, get_sanitized_filename("%s [%04d]" % (song['title'], k)), "metadata.json")

        package_metadata = song['package']

        if package_metadata:
            package_metadata['format'] = chart_format

            for k in ['sounds', 'bgm']:
                if 'dp_hyper' in package_metadata['charts'] and package_metadata['charts']['dp_hyper'][k]:
                    # Use DP Hyper sounds for missing charts DP charts
                    for k2 in ['dp_beginner', 'dp_normal', 'dp_another', 'dp_black']:
                        if k2 not in package_metadata['charts']:
                            continue

                        if not package_metadata['charts'][k2]['filename']:
                            del package_metadata['charts'][k2]
                            continue

                        if not package_metadata['charts'][k2][k]:
                            package_metadata['charts'][k2][k] = package_metadata['charts']['dp_hyper'][k]

                if 'sp_hyper' in package_metadata['charts'] and package_metadata['charts']['sp_hyper'][k]:
                    # Use SP Hyper sounds for remaining missing charts
                    for k2 in ['sp_beginner', 'sp_normal', 'sp_another', 'sp_black', 'dp_beginner', 'dp_normal', 'dp_hyper', 'dp_another', 'dp_black']:
                        if k2 not in package_metadata['charts']:
                            continue

                        if not package_metadata['charts'][k2]['filename']:
                            del package_metadata['charts'][k2]
                            continue

                        if not package_metadata['charts'][k2][k]:
                            package_metadata['charts'][k2][k] = package_metadata['charts']['sp_hyper'][k]

            for k in ['sounds', 'bgm', 'filename']:
                for k2 in ['sp_beginner', 'sp_normal', 'sp_another', 'sp_black', 'dp_beginner', 'dp_normal', 'dp_hyper', 'dp_another', 'dp_black']:
                    if k2 in package_metadata['charts']:
                        if k in package_metadata['charts'][k2]:
                            package_metadata['charts'][k2][k] = get_sanitized_filename(package_metadata['charts'][k2][k])

            if 'videos' in package_metadata:
                package_metadata['videos'] = [get_sanitized_filename(filename) for filename in package_metadata['videos']]

            if 'overlays' in package_metadata:
                package_metadata['overlays'] = get_sanitized_filename(package_metadata['overlays'])

            json.dump(package_metadata, open(metadata_filename, "w"), indent=4, ensure_ascii=False)

        iidxtool.process_file({
            'input': None,
            'input_format': chart_format,
            'output': output_filename,
            'output_format': 'json',
            'input_charts': song['charts'],
            'output_charts': {},
        })
