#!/usr/bin/env python3
# Modified by Raul Mur-Artal
# Automatically compute the optimal scale factor for monocular VO/SLAM.
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
#   pip install numpy matplotlib

"""
This script computes the absolute trajectory error from the ground truth
trajectory and the estimated trajectory.
"""

import sys
import numpy
import argparse

import associate  # Make sure associate.py is in the same folder or accessible

def align(model, data):
    """Align two trajectories using the method of Horn (closed-form).

    Input:
        model -- first trajectory (3xn)
        data -- second trajectory (3xn)

    Output:
        rot -- rotation matrix (3x3)
        trans -- translation vector (3x1)
        trans_error -- translational error per point (1xn)
    """
    numpy.set_printoptions(precision=3, suppress=True)
    model_zerocentered = model - model.mean(1)
    data_zerocentered = data - data.mean(1)

    W = numpy.zeros((3, 3))
    for column in range(model.shape[1]):
        W += numpy.outer(model_zerocentered[:, column], data_zerocentered[:, column])

    U, d, Vh = numpy.linalg.linalg.svd(W.transpose())
    S = numpy.matrix(numpy.identity(3))
    if (numpy.linalg.det(U) * numpy.linalg.det(Vh) < 0):
        S[2, 2] = -1
    rot = U * S * Vh
    rotmodel = rot * model_zerocentered

    dots = 0.0
    norms = 0.0
    for column in range(data_zerocentered.shape[1]):
        dots += numpy.dot(data_zerocentered[:, column].transpose(), rotmodel[:, column])
        normi = numpy.linalg.norm(model_zerocentered[:, column])
        norms += normi * normi
    s = float(dots / norms)

    transGT = data.mean(1) - s * rot * model.mean(1)
    trans = data.mean(1) - rot * model.mean(1)
    model_alignedGT = s * rot * model + transGT
    model_aligned = rot * model + trans

    alignment_errorGT = model_alignedGT - data
    alignment_error = model_aligned - data

    trans_errorGT = numpy.sqrt(numpy.sum(numpy.multiply(alignment_errorGT, alignment_errorGT), 0)).A[0]
    trans_error = numpy.sqrt(numpy.sum(numpy.multiply(alignment_error, alignment_error), 0)).A[0]

    return rot, transGT, trans_errorGT, trans, trans_error, s


def plot_traj(ax, stamps, traj, style, color, label):
    """
    Plot a trajectory using matplotlib.

    Input:
        ax -- the plot
        stamps -- time stamps (1xn)
        traj -- trajectory (3xn)
        style -- line style
        color -- line color
        label -- plot legend
    """
    stamps_sorted = sorted(stamps)
    interval = numpy.median([s - t for s, t in zip(stamps_sorted[1:], stamps_sorted[:-1])]) \
               if len(stamps_sorted) > 1 else 0
    x = []
    y = []
    if len(stamps_sorted) > 0:
        last = stamps_sorted[0]
    else:
        return

    for i in range(len(stamps)):
        if stamps[i] - last < 2 * interval:
            x.append(traj[i][0])
            y.append(traj[i][1])
        elif len(x) > 0:
            ax.plot(x, y, style, color=color, label=label)
            label = ""
            x = []
            y = []
        last = stamps[i]

    if len(x) > 0:
        ax.plot(x, y, style, color=color, label=label)


if __name__ == "__main__":
    # parse command line
    parser = argparse.ArgumentParser(description='''
    This script computes the absolute trajectory error from the ground truth trajectory
    and the estimated trajectory.
    ''')
    parser.add_argument('first_file',
                        help='ground truth trajectory (format: timestamp tx ty tz qx qy qz qw)')
    parser.add_argument('second_file',
                        help='estimated trajectory (format: timestamp tx ty tz qx qy qz qw)')
    parser.add_argument('--offset',
                        help='time offset added to the timestamps of the second file (default: 0.0)',
                        default=0.0)
    parser.add_argument('--scale',
                        help='scaling factor for the second trajectory (default: 1.0)',
                        default=1.0)
    parser.add_argument('--max_difference',
                        help='maximally allowed time difference for matching entries (default: 10000000 ns)',
                        default=20000000)
    parser.add_argument('--save',
                        help='save aligned second trajectory to disk (format: stamp2 x2 y2 z2)')
    parser.add_argument('--save_associations',
                        help='save associated first and aligned second trajectory to disk '
                             '(format: stamp1 x1 y1 z1 stamp2 x2 y2 z2)')
    parser.add_argument('--plot',
                        help='plot the first and the aligned second trajectory to an image (format: png)')
    parser.add_argument('--verbose',
                        help='print all evaluation data (otherwise, only the RMSE absolute translational error '
                             'in meters after alignment will be printed)',
                        action='store_true')
    parser.add_argument('--verbose2',
                        help='print scale error and RMSE absolute translational error in meters '
                             'after alignment with and without scale correction',
                        action='store_true')
    args = parser.parse_args()

    first_list = associate.read_file_list(args.first_file, False)
    second_list = associate.read_file_list(args.second_file, False)

    matches = associate.associate(first_list, second_list,
                                  float(args.offset),
                                  float(args.max_difference))

    if len(matches) < 2:
        sys.exit("Couldn't find matching timestamp pairs between groundtruth and estimated trajectory!"
                 " Did you choose the correct sequence?")

    # Build matrices of matched points
    first_xyz = numpy.matrix([[float(value) for value in first_list[a][0:3]] 
                              for a, b in matches]).transpose()
    second_xyz = numpy.matrix([[float(value)*float(args.scale) 
                                for value in second_list[b][0:3]] 
                               for a, b in matches]).transpose()

    # Sort the second_list by timestamp so we can build the full second_xyz
    sorted_second_list = sorted(second_list.items(), key=lambda x: x[0])
    second_xyz_full = numpy.matrix(
        [
            [float(value)*float(args.scale) for value in sorted_second_list[i][1][0:3]] 
            for i in range(len(sorted_second_list))
        ]
    ).transpose()

    # Perform alignment
    rot, transGT, trans_errorGT, trans, trans_error, scale = align(second_xyz, first_xyz)

    # Aligned second trajectory (with scale correction)
    second_xyz_aligned = scale * rot * second_xyz + trans
    # Aligned second trajectory (without scale correction)
    second_xyz_notscaled = rot * second_xyz + trans
    second_xyz_notscaled_full = rot * second_xyz_full + trans

    # Build full matrices for the first_xyz_full and second_xyz_full
    first_stamps = sorted(first_list.keys())
    first_xyz_full = numpy.matrix(
        [[float(value) for value in first_list[b][0:3]] 
         for b in first_stamps]
    ).transpose()

    second_stamps = sorted(second_list.keys())
    second_xyz_full = numpy.matrix(
        [[float(value)*float(args.scale) for value in second_list[b][0:3]]
         for b in second_stamps]
    ).transpose()

    second_xyz_full_aligned = scale * rot * second_xyz_full + trans

    # Print results
    if args.verbose:
        print(f"compared_pose_pairs {len(trans_error)} pairs")
        print(f"absolute_translational_error.rmse {numpy.sqrt(numpy.dot(trans_error, trans_error) / len(trans_error))} m")
        print(f"absolute_translational_error.mean {numpy.mean(trans_error)} m")
        print(f"absolute_translational_error.median {numpy.median(trans_error)} m")
        print(f"absolute_translational_error.std {numpy.std(trans_error)} m")
        print(f"absolute_translational_error.min {numpy.min(trans_error)} m")
        print(f"absolute_translational_error.max {numpy.max(trans_error)} m")
        print(f"max idx: {numpy.argmax(trans_error)}")
    else:
        # RMSE with scale correction, scale factor, and RMSE without scale correction
        rmse_scale = numpy.sqrt(numpy.dot(trans_error, trans_error) / len(trans_error))
        rmse_no_scale = numpy.sqrt(numpy.dot(trans_errorGT, trans_errorGT) / len(trans_errorGT))
        print(f"{rmse_scale},{scale},{rmse_no_scale}")

    if args.verbose2:
        print(f"compared_pose_pairs {len(trans_error)} pairs")
        print(f"absolute_translational_error.rmse {numpy.sqrt(numpy.dot(trans_error, trans_error) / len(trans_error))} m")
        print(f"absolute_translational_errorGT.rmse {numpy.sqrt(numpy.dot(trans_errorGT, trans_errorGT) / len(trans_errorGT))} m")

    # Save associations if requested
    if args.save_associations:
        with open(args.save_associations, "w") as f:
            f.write("\n".join([
                f"{a:.6f} {x1:.6f} {y1:.6f} {z1:.6f} {b:.6f} {x2:.6f} {y2:.6f} {z2:.6f}"
                for (a, b), (x1, y1, z1), (x2, y2, z2) in zip(
                    matches,
                    first_xyz.transpose().A,
                    second_xyz_aligned.transpose().A
                )
            ]))

    # Save aligned second trajectory if requested
    if args.save:
        with open(args.save, "w") as f:
            f.write("\n".join([
                f"{stamp:.6f} " + " ".join([f"{d:.6f}" for d in line])
                for stamp, line in zip(second_stamps,
                                       second_xyz_notscaled_full.transpose().A)
            ]))

    # Plot if requested
    if args.plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig = plt.figure()
        ax = fig.add_subplot(111)
        plot_traj(ax, first_stamps, first_xyz_full.transpose().A, '-', "black", "ground truth")
        plot_traj(ax, second_stamps, second_xyz_full_aligned.transpose().A, '-', "blue", "estimated")

        label = "difference"
        for (a, b), (x1, y1, z1), (x2, y2, z2) in zip(matches,
                                                     first_xyz.transpose().A,
                                                     second_xyz_aligned.transpose().A):
            ax.plot([x1, x2], [y1, y2], '-', color="red", label=label)
            label = ""

        ax.legend()
        ax.set_xlabel('x [m]')
        ax.set_ylabel('y [m]')
        plt.axis('equal')
        plt.savefig(args.plot, format="pdf")

