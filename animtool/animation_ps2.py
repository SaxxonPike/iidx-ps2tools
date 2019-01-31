# pylint: disable=missing-docstring

import json
import os
import queue
import threading

from PIL import Image

import animtool.imageops as imageops
import animtool.sprites as sprites


def get_base_frame_from_animation(animation):
    base_frame = {
        'w': 640,
        'h': 480,
    }

    if animation is None:
        return base_frame

    for frame in animation['frames']:
        if frame['anim_type'] == 65535:
            base_frame['w'] = frame['x'] * 2
            base_frame['h'] = frame['y'] * 2
            base_frame['start_frame'] = frame['start_frame']
            base_frame['end_frame'] = frame['end_frame']
            break

    return base_frame


def get_nearest_key(keys, frame_idx):
    nearest_frame_idx = frame_idx

    if nearest_frame_idx not in keys:
        for k in sorted(keys):
            if k < frame_idx:
                nearest_frame_idx = k

    return nearest_frame_idx


class AnimationPs2:
    def __init__(self, filename, threads, debug=False):
        self.threads = threads
        self.debug = debug

        self.sprite_elements = []

        filenames = sprites.extract_files(filename)

        self.sprite_elements = sprites.extract_sprite_elements(filenames)
        self.animation_list = sprites.get_animation_info(filenames[0])

        for extracted_filename in filenames:
            if os.path.exists(extracted_filename):
                os.unlink(extracted_filename)


    def __del__(self):
        self.cleanup()


    def render_zoom(self, frame, frame_idx, frame_x, frame_y, base_center_x, base_center_y, target_sprite):
        zooms_frame_idx = get_nearest_key(frame['zooms'].keys(), frame_idx)
        if zooms_frame_idx in frame['zooms']:
            scale_x = frame['zooms'][zooms_frame_idx]['scale_x']
            scale_y = frame['zooms'][zooms_frame_idx]['scale_y']
            new_w = target_sprite.width * scale_x
            new_h = target_sprite.height * scale_y

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

            frame_x += (frame_x - base_center_x) * (abs(frame['zooms'][zooms_frame_idx]['scale_x']) - 1)
            frame_y += (frame_y - base_center_y) * (abs(frame['zooms'][zooms_frame_idx]['scale_y']) - 1)

            target_sprite.close()
            del target_sprite
            target_sprite = target_sprite2

        return target_sprite, frame_x, frame_y


    def render_rotation(self, frame, frame_idx, frame_x, frame_y, target_sprite):
        rotations_frame_idx = get_nearest_key(frame['rotations'].keys(), frame_idx)
        rotation = 0.0
        if rotations_frame_idx in frame['rotations']:
            rotation = frame['rotations'][rotations_frame_idx]['rotation']

            old_size = target_sprite.size
            target_sprite2 = target_sprite.rotate(-rotation, expand=True)

            target_sprite.close()
            del target_sprite
            target_sprite = target_sprite2

            frame_x -= (target_sprite.size[0] - old_size[0]) / 2
            frame_y -= (target_sprite.size[1] - old_size[1]) / 2

        return target_sprite, frame_x, frame_y


    def render_position(self, frame, frame_idx, frame_x, frame_y, base_center_x, base_center_y):
        positions_frame_idx = get_nearest_key(frame['position'].keys(), frame_idx)
        if positions_frame_idx in frame['position']:
            frame_x += frame['position'][positions_frame_idx]['x'] - base_center_x
            frame_y += frame['position'][positions_frame_idx]['y'] - base_center_y

        return frame_x, frame_y


    def render_fades(self, frame, frame_idx):
        fades_frame_idx = get_nearest_key(frame['fades'].keys(), frame_idx)
        opacity = None
        if fades_frame_idx in frame['fades']:
            opacity = frame['fades'][fades_frame_idx]

        if frame['anim_type'] != 0 and frame['opacity'] != 1.0:
            if opacity:
                opacity['opacity'] *= frame['opacity']

            else:
                opacity = {
                    'opacity': frame['opacity'],
                    'opacity2': 1.0,
                }

        return opacity


    def render_frame(self, frame, frame_idx, base_image_w, base_image_h):
        if isinstance(self.sprite_elements[frame['anim_id']], str):
            target_sprite = Image.open(self.sprite_elements[frame['anim_id']]).convert("RGBA")
        else:
            target_sprite = self.sprite_elements[frame['anim_id']].copy()

        if frame['anim_format'] == 1:
            rendered_sprite = Image.new('RGBA', target_sprite.size, (0, 0, 0, 0))
            black_bg = Image.new('RGBA', target_sprite.size, (0, 0, 0, 255))
            rendered_sprite.paste(black_bg, (0, 0), target_sprite.convert("L"))

            black_bg.close()
            del black_bg

            target_sprite.close()
            del target_sprite

            target_sprite = rendered_sprite

        base_center_x = base_image_w / 2
        base_center_y = base_image_h / 2

        frame_x = base_center_x - frame['x']
        frame_y = base_center_y - frame['y']

        target_sprite, frame_x, frame_y = self.render_zoom(frame, frame_idx, frame_x, frame_y, base_center_x, base_center_y, target_sprite)
        target_sprite, frame_x, frame_y = self.render_rotation(frame, frame_idx, frame_x, frame_y, target_sprite)
        frame_x, frame_y = self.render_position(frame, frame_idx, frame_x, frame_y, base_center_x, base_center_y)
        opacity = self.render_fades(frame, frame_idx)

        return target_sprite, int(frame_x), int(frame_y), opacity


    def get_animation_by_id(self, animation_id):
        for animation in self.animation_list:
            if animation['anim_id'] == animation_id:
                return animation

        return None


    def render_subanimations(self, animation, frame_idx, parent_anim_format=-1):
        if animation is None or len(animation['frames']) <= 1:
            return None

        print("Rendering frame %d of animaton %d" % (frame_idx, animation['anim_id']))

        base_frame = get_base_frame_from_animation(animation)

        rendered_frame = Image.new('RGBA', (base_frame['w'], base_frame['h']), (0, 0, 0, 255 if parent_anim_format == -1 else 0))

        for frame in animation['frames']:
            if frame_idx < frame['start_frame'] or frame_idx >= frame['end_frame']:
                continue

            if frame['anim_type'] == 65535:
                continue

            if frame['anim_type'] not in [0, 1, 2, 3, 65535]:
                print("Unknown animation type:", frame['anim_type'])
                exit(1)

            if frame['anim_type'] == 3:
                # What is this even?
                continue

            if frame['anim_type'] == 2:
                # Animation reference
                target_animation = self.get_animation_by_id(frame['anim_id'])
                target_frame_idx = frame_idx - frame['start_frame'] + frame['frame_offset']
                image = self.render_subanimations(target_animation, target_frame_idx, frame['anim_format'])

                if not image:
                    continue

                ref_frame = {}
                ref_frame['anim_type'] = frame['anim_type']
                ref_frame['anim_id'] = len(self.sprite_elements)
                ref_frame['orig_anim_id'] = frame['anim_id']
                ref_frame['anim_format'] = frame['anim_format']
                ref_frame['position'] = {}
                ref_frame['zooms'] = {}
                ref_frame['fades'] = {}
                ref_frame['rotations'] = {}
                ref_frame['opacity'] = frame['opacity']
                ref_frame['x'] = frame['x']
                ref_frame['y'] = frame['y']
                ref_frame['start_frame'] = frame_idx
                ref_frame['end_frame'] = frame_idx
                ref_frame['frame_offset'] = frame['frame_offset']

                for key in ['position', 'zooms', 'fades', 'rotations']:
                    nearest_frame_idx = get_nearest_key(frame[key].keys(), frame_idx)
                    if nearest_frame_idx in frame[key]:
                        ref_frame[key][frame_idx] = frame[key][nearest_frame_idx]

                frame = ref_frame

                self.sprite_elements.append(image)

            image, sprite_x, sprite_y, opacity = self.render_frame(frame, frame_idx, base_frame['w'], base_frame['h'])

            if not image:
                return None

            if frame['anim_type'] == 2:
                self.sprite_elements[frame['anim_id']].close()

            # Render sprite where it needs to be in a full framed image
            rendered_frame_internal = Image.new('RGBA', (base_frame['w'], base_frame['h']), (0, 0, 0, 0))
            rendered_frame_internal.paste(image, (sprite_x, sprite_y))
            image.close()
            del image
            image = rendered_frame_internal

            if frame['anim_format'] == 0:
                if opacity:
                    rendered_frame = imageops.image_blend_2(image, rendered_frame, opacity['opacity'], opacity['opacity2'])

                else:
                    rendered_frame.alpha_composite(image, (0, 0))

            elif frame['anim_format'] == 1:
                mask2 = image.copy()

                if opacity:
                    target_sprite = image
                    alpha_bg = Image.new(target_sprite.mode, target_sprite.size, (0, 0, 0, 0))
                    target_sprite2 = Image.blend(alpha_bg, target_sprite, opacity['opacity'])

                    target_sprite.close()
                    alpha_bg.close()
                    del alpha_bg
                    del target_sprite

                    image = target_sprite2

                rendered_frame2 = Image.new('RGBA', (base_frame['w'], base_frame['h']), (0, 0, 0, 0))
                black_bg = Image.new('RGBA', image.size, (0, 0, 0, 255))
                mask2 = image
                rendered_frame2.paste(black_bg, (0, 0), mask2)
                rendered_frame.alpha_composite(rendered_frame2, (0, 0))

                black_bg.close()
                del black_bg

                mask2.close()
                del mask2

                rendered_frame2.close()
                del rendered_frame2

            elif frame['anim_format'] == 2:
                if not opacity:
                    opacity = {
                        'opacity': 1.0,
                        'opacity2': 1.0,
                    }

                if parent_anim_format == -1:
                    rendered_frame = imageops.image_blend_2(image, rendered_frame, opacity['opacity'], opacity['opacity2'])

                else:
                    rendered_frame = imageops.image_blend_1(image, rendered_frame, opacity['opacity'], opacity['opacity2'])

            else:
                print("Unimplemented animation type")
                print(animation['anim_id'], frame)
                exit(1)

            image.close()
            del image

        return rendered_frame.copy()


    def render_worker(self, animation_id, target_start_frame, target_end_frame, output_folder=None, fast_mode=False, force_stored_temp_frames=False):
        animation = self.get_animation_by_id(animation_id)

        if animation is None:
            print("Couldn't find animation %d, skipping..." % animation_id)
            return

        base_frame = get_base_frame_from_animation(animation)

        start_frame = base_frame['start_frame']
        end_frame = base_frame['end_frame']

        if target_start_frame and target_start_frame >= start_frame and target_start_frame <= end_frame:
            start_frame = target_start_frame

        if target_end_frame and target_end_frame >= start_frame and target_end_frame <= end_frame:
            end_frame = target_end_frame

        output_filename = "output_%04d.gif" % animation['anim_id']

        if output_folder:
            output_filename = os.path.join(output_folder, output_filename)

        print("Rendering animation %d to %s" % (animation['anim_id'], output_filename))

        if fast_mode:
            # ImageIO's support for gifs leaves much to be desired, but this gives the best performance overall
            # Upsides: Fast, streaming GIF creation, so no need to save all frames until end to create GIF
            # Downsides: Color support is really bad using GIF-PIL, and GIF-FI has issues with setting the FPS/frame duration
            import imageio
            import numpy
            with imageio.get_writer(output_filename.replace("gif", "mp4"), mode='I', fps=60, quality=10, format='FFMPEG') as writer:
                for frame_idx in range(start_frame, end_frame):
                    rendered_frame = Image.new('RGBA', (base_frame['w'], base_frame['h']), (0, 0, 0, 0))
                    rendered_frame = self.render_subanimations(animation, frame_idx)
                    writer.append_data(numpy.asarray(rendered_frame, dtype='uint8'))
                    rendered_frame.close()
                    del rendered_frame

        else:
            # Store all frames until end and create a WebP or GIF
            # Upsides: Good quality
            # Downsides: Uses lots of memory or disk space (depending on animation being rendered)
            import psutil
            import tempfile
            from io import BytesIO
            # Determine whether or not we should store to disk based on free memory and max frame size and number of frames
            should_store_temp_frames = False

            allowed_memory_use_percentage = 0.25 # Allow 25% of free memory to be used, mostly because you have to load all frames into memory at the end to create the gif/webp anyway
            available_memory = psutil.virtual_memory().free
            available_swap = psutil.swap_memory().free
            available_total = available_memory + available_swap
            raw_frame_size = base_frame['w'] * base_frame['h'] * 4 # Since all images are going to be RGBA, use 4
            total_frames = end_frame - start_frame
            total_frames_size = total_frames * raw_frame_size

            if total_frames_size > available_total * allowed_memory_use_percentage:
                should_store_temp_frames = True

            if force_stored_temp_frames:
                should_store_temp_frames = force_stored_temp_frames

            if should_store_temp_frames:
                print("Will save render frames to temporary files")
            else:
                print("Will save render frames to memory")

            prerenders = []
            for frame_idx in range(start_frame, end_frame):
                rendered_frame = self.render_subanimations(animation, frame_idx)

                # Save rendered frame to disk if the number of frames is greater than reasonable for the system
                if should_store_temp_frames:
                    temp_file, filename = tempfile.mkstemp(suffix=".png")
                    os.close(temp_file)
                    rendered_frame.save(filename, format="png", compress_level=0)
                    prerenders.append(filename)

                    rendered_frame.close()
                    del rendered_frame
                else:
                    prerenders.append(rendered_frame)

            if prerenders:
                frames = []
                print("Loading all frames into memory...")
                for obj in prerenders:
                    if isinstance(obj, str):
                        image = Image.open(obj)

                        image_data = BytesIO()
                        image.save(image_data, format="png")

                        image.close()
                        del image

                        image = Image.open(image_data)
                        frames.append(image)

                    else:
                        frames.append(obj)

                # output_filename_webp = output_filename.replace("gif", "webp")
                # print("Saving WebP render...", output_filename_webp)
                # frames[0].save(output_filename_webp, format="webp", save_all=True, append_images=frames[1:], loop=0, lossless=True, quality=0, duration=round((1/60)*1000))

                print("Saving GIF render...", output_filename)
                frames[0].save(output_filename, format="gif", save_all=True, append_images=frames[1:], loop=0xffff, lossless=True, quality=0, duration=round((1/60)*1000))

                for frame in frames:
                    frame.close()
                    del frame

            for filename in prerenders:
                if isinstance(filename, str):
                    os.unlink(filename)


    def render(self, animation_ids=None, output_folder=None, fast_mode=False):
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        if self.debug:
            json.dump(self.animation_list, open(os.path.join(output_folder, "debug.json"), "w"), indent=4)

        if isinstance(animation_ids, int):
            animation_ids = [(animation_ids, None, None)]

        elif isinstance(animation_ids, list):
            if not animation_ids:
                animation_ids = [(animation['anim_id'], None, None) for animation in self.animation_list]
            else:
                animation_ids = [(x, None, None) for x in animation_ids]

        else:
            animation_ids = [(animation['anim_id'], None, None) for animation in self.animation_list]

        def thread_worker():
            while True:
                item = queue_data.get()

                if item is None:
                    break

                animation_id, target_start_frame, target_end_frame, output_folder, fast_mode = item
                self.render_worker(animation_id, target_start_frame, target_end_frame, output_folder, fast_mode)

                queue_data.task_done()

        queue_data = queue.Queue()
        threads = []
        for _ in range(self.threads):
            thread = threading.Thread(target=thread_worker)
            thread.start()
            threads.append(thread)

        for animation_id, target_start_frame, target_end_frame in animation_ids:
            queue_data.put((animation_id, target_start_frame, target_end_frame, output_folder, fast_mode))

        queue_data.join()

        for _ in range(self.threads):
            queue_data.put(None)

        for thread in threads:
            thread.join()

        self.cleanup()


    def cleanup(self):
        for sprite_element in self.sprite_elements:
            if isinstance(sprite_element, str) and os.path.exists(sprite_element):
                os.unlink(sprite_element)

        self.sprite_elements = []
