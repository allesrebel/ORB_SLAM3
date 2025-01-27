#!/usr/bin/env python3
# Software License Agreement (BSD License)
#
# Copyright (c) 2013, Juergen Sturm, TUM
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of TUM nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Requirements:
#   pip install numpy argparse

"""
The Kinect provides the color and depth images in an un-synchronized way.
This means that the set of time stamps from the color images do not
intersect with those of the depth images. Therefore, we need some way
of associating color images to depth images.

For this purpose, you can use the ''associate.py'' script. It reads the
time stamps from the rgb.txt file and the depth.txt file, and joins them
by finding the best matches.
"""

import argparse
import sys
import numpy

def read_file_list(filename, remove_bounds=False):
    """
    Reads a trajectory from a text file.

    File format:
        The file format is "stamp d1 d2 d3 ...", where stamp denotes the
        time stamp (to be matched) and "d1 d2 d3.." is arbitrary data
        (e.g., a 3D position and 3D orientation) associated to this timestamp.

    Input:
        filename -- File name
        remove_bounds -- Whether to drop the first/last entries (default: False)

    Output:
        A dict with:
          key: float(timestamp)
          value: list of strings with the data columns
    """
    with open(filename, 'r') as f:
        lines = f.read().replace(",", " ").replace("\t", " ").split("\n")

    if remove_bounds:
        lines = lines[100:-100]

    cleaned = []
    for line in lines:
        line = line.strip()
        if len(line) == 0 or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) > 1:
            # first item = stamp, the rest are data
            cleaned.append((float(parts[0]), parts[1:]))

    return dict(cleaned)


def associate(first_list, second_list, offset, max_difference):
    """
    Associate two dictionaries of (stamp, data). As the time stamps
    never match exactly, we aim to find the closest match for every input tuple.

    Input:
        first_list -- dict of (stamp, data)
        second_list -- dict of (stamp, data)
        offset -- time offset added to the timestamps of the second list
        max_difference -- search radius for candidate generation

    Output:
        matches -- list of matched tuples:
          [ (stamp1, stamp2), (stamp1, stamp2), ... ]
        where stamp1 is from first_list, stamp2 is from second_list
    """
    # Convert dict.keys() into sets so we can safely remove matched stamps
    first_keys = set(first_list.keys())
    second_keys = set(second_list.keys())

    # Generate all potential matches (where time difference < max_difference)
    potential_matches = []
    for a in first_keys:
        for b in second_keys:
            if abs(a - (b + offset)) < max_difference:
                potential_matches.append((abs(a - (b + offset)), a, b))

    # Sort by absolute difference
    potential_matches.sort(key=lambda x: x[0])

    matches = []
    for diff, a, b in potential_matches:
        if (a in first_keys) and (b in second_keys):
            # we've found a match
            first_keys.remove(a)
            second_keys.remove(b)
            matches.append((a, b))

    # Finally, sort the matches by the first stamp
    matches.sort(key=lambda x: x[0])
    return matches


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='''
This script takes two data files (each containing lines of:
timestamp data1 data2 data3 ...) and associates their timestamps.
''')
    parser.add_argument('first_file',  help='first text file (format: timestamp data)')
    parser.add_argument('second_file', help='second text file (format: timestamp data)')
    parser.add_argument('--first_only', help='only output associated lines from first file',
                        action='store_true')
    parser.add_argument('--offset', help='time offset added to the timestamps of the second file (default: 0.0)',
                        default=0.0)
    parser.add_argument('--max_difference', help='maximally allowed time difference for matching entries (default: 0.02)',
                        default=0.02)
    parser.add_argument('--remove_bounds', help='drop first and last 100 lines from each file', 
                        action='store_true')
    args = parser.parse_args()

    # Read the two files
    first_list = read_file_list(args.first_file, remove_bounds=args.remove_bounds)
    second_list = read_file_list(args.second_file, remove_bounds=args.remove_bounds)

    # Do the matching
    matches = associate(first_list, second_list,
                        float(args.offset),
                        float(args.max_difference))

    # Print results
    if args.first_only:
        for a, b in matches:
            data_a = " ".join(first_list[a])
            print(f"{a:.6f} {data_a}")
    else:
        for a, b in matches:
            data_a = " ".join(first_list[a])
            data_b = " ".join(second_list[b])
            # Subtract offset from b for output if you want the "second" stamp
            # to reflect the un-offset time
            print(f"{a:.6f} {data_a} {b - float(args.offset):.6f} {data_b}")

