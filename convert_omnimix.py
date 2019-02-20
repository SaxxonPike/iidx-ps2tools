import glob
import hashlib
import json
import os
import shutil
import struct
import sys
import subprocess

import iidxtool
import parse_wvb

OUTPUT_FORMAT = "25thac"

def get_filesize(filename):
    filesize = 0

    with open(filename, "rb") as infile:
        infile.seek(0, 2)
        return infile.tell()


def create_s3p(input_folder, output_filename):
    with open(output_filename, "wb") as outfile:
        outfile.write(b"S3P0")

        files = sorted(glob.glob(os.path.join(glob.escape(input_folder), "*.asf")))

        outfile.write(struct.pack("<I", len(files)))

        offset = len(files) * 8 + 8
        for i in range(len(files)):
            filesize = get_filesize(files[i]) + 0x20
            outfile.write(struct.pack("<II", offset, filesize))
            offset += filesize

        for i in range(len(files)):
            with open(files[i], "rb") as infile:
                data = infile.read()
                filesize = len(data)
                data_hash = 0

                outfile.write(b"S3V0")
                outfile.write(struct.pack("<III", 0x20, filesize, data_hash))
                outfile.write("".join(['\0'] * 16).encode('ascii'))
                outfile.write(data)


for game_folder in glob.glob(glob.escape(sys.argv[1]) + "//*"):
    game = os.path.basename(game_folder)[2:] + "cs"

    for song_folder in glob.glob(glob.escape(game_folder) + "//*"):
        song_metadata = json.load(open(os.path.join(song_folder, "metadata.json")))

        if not os.path.exists(os.path.join(song_folder, "package")):
            os.makedirs(os.path.join(song_folder, "package"))

        package_metadata = {
            "_videos": [],
            "_overlays": [],
            "_charts": [],
            "_sounds": [],

            "song_id": 0,
            "title": song_metadata['title'],
            "title_ascii": song_metadata['title'],
            "genre": "",
            "artist": "",
            "texture_title": 0,
            "texture_artist": 0,
            "texture_genre": 0,
            "texture_load": 0,
            "texture_list": 0,
            "font_idx": 0,
            "game_version": 0,
            "other_folder": 0,
            "bemani_folder": 0,
            "splittable_diff": 0,
            "difficulties": [0, 0, 0, 0, 0, 0, 0, 0],
            "volume": 100,
            "file_identifiers": [],
            "bga_filename": "",
            "bga_delay": 0,
            "afp_flag": 0,
            "afp_data": [ "0" * 64 ] * 10,
        }

        # Convert chart to .1
        output_chart_filename = os.path.join(song_folder, "package", os.path.basename(song_folder) + ".1")

        chart_args = ['--output-format', OUTPUT_FORMAT]
        chart_args += ['--output', output_chart_filename]

        chart_args += ['--input-format', song_metadata['format']]
        for k in song_metadata['charts']:
            if 'black' in k:
                continue

            chart_args.append("--input-" + k.replace("_", "-"))
            chart_args.append(os.path.join(song_folder, song_metadata['charts'][k]['filename']))

        iidxtool.main(chart_args)

        package_metadata['_charts'].append(os.path.basename(output_chart_filename))
        package_metadata['_videos'].append(song_metadata['videos'][0])

        # Extract audio files here
        parsed_files = []
        part_list = ['sp', 'dp']
        difficulty_list = ['normal', 'hyper', 'another', 'beginner'] # Figure out how to handle black charts here... create legg chart?
        for part in part_list:
            for difficulty in difficulty_list:
                k = "{}_{}".format(part, difficulty)

                if k not in song_metadata['charts']:
                    package_metadata['file_identifiers'].append(48) # 0
                    continue

                wvb_filename = os.path.join(song_folder, song_metadata['charts'][k]['sounds'])
                pcm_filename = os.path.join(song_folder, song_metadata['charts'][k]['bgm'])

                sounds_foldername = "sounds_{}".format(len(parsed_files))
                output_path = os.path.join(song_folder, sounds_foldername)
                output_s3p = os.path.join(song_folder, "package", sounds_foldername + ".s3p")

                # Add some file hashing here to determine if the files really are different or not instead of using filenames
                wvb_checksum = hashlib.md5(open(wvb_filename, "rb").read()).hexdigest()
                pcm_checksum = hashlib.md5(open(pcm_filename, "rb").read()).hexdigest()
                if (wvb_checksum, pcm_checksum) not in parsed_files:
                    # parse_wvb.main(['--input', wvb_filename, '--output', output_path, '--output-frame-rate', '44100', '--output-sample-width', '16'])
                    # parse_wvb.convert_vgmstream(pcm_filename, os.path.join(output_path, "0001.wav"), None, 44100, 16, None)

                    parse_wvb.main(['--input', wvb_filename, '--output', output_path, '--output-format', 'asf', '--output-frame-rate', '44100', '--output-sample-width', '16', '--output-bitrate', '160K'])
                    parse_wvb.convert_vgmstream(pcm_filename, os.path.join(output_path, "0001.wav"), "asf", 44100, 16, "160K", fix_samples=True)
                    create_s3p(output_path, output_s3p)

                    package_metadata['_sounds'].append(os.path.basename(output_s3p))

                    parsed_files.append((wvb_checksum, pcm_checksum))

                    shutil.rmtree(output_path)

                package_metadata['file_identifiers'].append(ord('{}'.format(parsed_files.index((wvb_checksum, pcm_checksum)))))

                if difficulty == 'beginner':
                    package_metadata['difficulties'][6 + part_list.index(part)] = song_metadata['charts'][k]['difficulty']

                else:
                    package_metadata['difficulties'][3 * part_list.index(part) + difficulty_list.index(difficulty)] = song_metadata['charts'][k]['difficulty']

        for video_filename in package_metadata['_videos']:
            shutil.copyfile(os.path.join(song_folder, video_filename), os.path.join(song_folder, "package", video_filename))

        # TODO: Convert overlay to afp here

        # Save package file
        print(package_metadata)
        json.dump(package_metadata, open(os.path.join(song_folder, "package", "package.json"), "w"), ensure_ascii=False, indent=4)
