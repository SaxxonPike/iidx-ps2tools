# pylint: disable=missing-docstring

import argparse

from animtool.animation_ps2 import AnimationPs2

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', help='Input file')
    parser.add_argument('--output', help='Output folder')
    parser.add_argument('--threads', help='Number of threads to use for rendering separate animations', type=int, default=8)
    parser.add_argument('--animation-ids', nargs='+', help='IDs of animations to render. Will render all animations if not set.', type=int, default=None)
    parser.add_argument('--debug', help='Save raw animation list data to debug.json', action='store_true', default=False)
    parser.add_argument('--fast', help='Use a quick and dirty way of saving GIF file with reduced quality', action='store_true', default=False)
    args = parser.parse_args()

    animparser = AnimationPs2(args.input, args.threads, args.debug)
    animparser.render(args.animation_ids, args.output, args.fast)
