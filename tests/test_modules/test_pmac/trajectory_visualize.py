"""
This module is used for investigating trajectories in isolation of a pmac.
It simulates the velocity calculations that would have been performed by
PROG1 and plots all the points in a trajectory with velocity vectors.
"""
import matplotlib.pyplot as plt
import numpy as np
from enum import IntEnum


class VelMode(IntEnum):
    PrevNext = 0
    PrevCurrent = 1
    CurrentNext = 2
    Zero = 3


def velocity_prev_next(previous_pos, current_pos, next_pos,
                       prev_time, current_time):
    # new proportional P->N velocity calculation
    speed1 = (current_pos - previous_pos) / prev_time
    speed2 = (next_pos - current_pos) / current_time
    return (speed1 + speed2) / 2


def velocity_current_next(current_pos, next_pos, current_time):
    # redundant - now always use prev_current
    return (next_pos - current_pos) / current_time


def velocity_prev_current(previous_pos, previous_velocity, current_pos,
                          previous_time):
    result, dt2 = 0, 0
    if previous_time != 0:
        dt2 = 2.0 * (current_pos - previous_pos) / previous_time
        result = dt2 - previous_velocity
    return result


def plot_velocities(np_arrays, title='Plot', step_time=0.15):
    """ plots a 2d graph of a 2 axis trajectory, also does the velocity
    calculations and plots the velocity vector at each point.
    """
    xs, ys, ts, modes, user = np_arrays
    fig1 = plt.figure(figsize=(8, 6), dpi=300)
    plt.title(title)

    # a multiply in ms for the velocity vectors
    # uses 80% so that we can see the ends of the vectors in staight lines
    ms = step_time / 2 * 1000000 * .80

    # plot some velocity vectors
    vxs = np.zeros(len(xs))
    vys = np.zeros(len(xs))
    velocity_colors = ['#ff808060', '#80ff8060', '#8080ff60', '#80ffff60']
    for i in range(1, len(xs) - 1):
        if modes[i] == VelMode.PrevNext:
            vxs[i] = velocity_prev_next(xs[i - 1], xs[i], xs[i + 1], ts[i],
                                        ts[i])
            vys[i] = velocity_prev_next(ys[i - 1], ys[i], ys[i + 1], ts[i],
                                        ts[i + 1])
        elif modes[i] == VelMode.PrevCurrent:
            vxs[i] = velocity_prev_current(xs[i - 1], vxs[i - 1], xs[i],
                                           ts[i])
            vys[i] = velocity_prev_current(ys[i - 1], vys[i - 1], ys[i],
                                           ts[i])
        elif modes[i] == VelMode.CurrentNext:
            vxs[i] = velocity_current_next(xs[i], xs[i + 1], ts[i])
            vys[i] = velocity_current_next(ys[i], ys[i + 1], ts[i])

        # plot a line to represent the velocity vector
        print('velocity vector:', xs[i], ys[i], vxs[i] * ms, vys[i] * ms)
        plt.plot([xs[i], xs[i] + vxs[i] * ms],
                 [ys[i], ys[i] + vys[i] * ms],
                 color=velocity_colors[i % len(velocity_colors)])

    # plot the start and end positions
    plt.plot([xs[0]], [ys[0]], 'go')
    plt.plot([xs[-1]], [ys[-1]], 'ro')
    # plot capture and bounds points altogether
    plt.plot(xs, ys, linestyle="", marker=".", color="k", markersize=2)

    for i in range(len(user)):
        if user[i] == 4:
            # plot over the data points with a plus
            plt.plot(xs[i], ys[i], marker="+", color="k", markersize=5)

    fig1.show()
