#!/usr/bin/env python3

import time
import struct
import zenoh
import os
import math
import numpy as np
from typing import Literal

broadcast_type: Literal[
    "kinematics",
    "gyro",
    "altitude",
] = os.environ.get("DUMMY_BROADCAST_TYPE", "kinematics")

INITIAL_VELOCITY = 100.0
GRAVITY = 9.81
LAUNCH_ANGLE = math.radians(75)

V0_X = INITIAL_VELOCITY * math.cos(LAUNCH_ANGLE)
V0_Y = INITIAL_VELOCITY * math.sin(LAUNCH_ANGLE)

FLIGHT_TIME = 2 * V0_Y / GRAVITY
MAX_ALTITUDE = (V0_Y**2) / (2 * GRAVITY)

NOISE_COVARIANCES = {
    "kinematics": {
        "position_x": 100,
        "position_y": 100,
        "velocity_x": 100,
        "velocity_y": 100,
        "acceleration_x": 100,
        "acceleration_y": 100,
    },
    "altitude": {
        "altitude": 1.0,
    },
    "gyro": {
        "omega_x": 0.01,
        "omega_y": 0.01,
        "omega_z": 0.01,
    },
}


def get_position(t: float) -> tuple[float, float]:
    x = V0_X * t
    y = V0_Y * t - 0.5 * GRAVITY * t * t
    return x, y


def get_velocity(t: float) -> tuple[float, float]:
    vx = V0_X
    vy = V0_Y - GRAVITY * t
    return vx, vy


def get_altitude(t: float) -> float:
    return V0_Y * t - 0.5 * GRAVITY * t * t


def get_acceleration(t: float) -> tuple[float, float]:
    return 0.0, -GRAVITY


def get_angular_velocity(t: float) -> tuple[float, float, float]:
    phase = t * 2 * math.pi / FLIGHT_TIME
    omega_x = 0.5 * math.sin(phase)
    omega_y = 0.3 * math.cos(phase * 1.5)
    omega_z = 0.8 * math.sin(phase * 0.7)
    return omega_x, omega_y, omega_z


def add_noise(value: float, std_dev: float) -> float:
    return value + np.random.normal(0, std_dev)


def get_noisy_kinematics(t: float) -> tuple[float, float, float, float, float, float]:
    x, y = get_position(t)
    vx, vy = get_velocity(t)
    ax, ay = get_acceleration(t)

    cov = NOISE_COVARIANCES["kinematics"]
    x_noisy = add_noise(x, math.sqrt(cov["position_x"]))
    y_noisy = add_noise(y, math.sqrt(cov["position_y"]))
    vx_noisy = add_noise(vx, math.sqrt(cov["velocity_x"]))
    vy_noisy = add_noise(vy, math.sqrt(cov["velocity_y"]))
    ax_noisy = add_noise(ax, math.sqrt(cov["acceleration_x"]))
    ay_noisy = add_noise(ay, math.sqrt(cov["acceleration_y"]))

    return x_noisy, y_noisy, vx_noisy, vy_noisy, ax_noisy, ay_noisy


def serialize_kinematics(t: float) -> bytes:
    x_noisy, y_noisy, vx_noisy, vy_noisy, ax_noisy, ay_noisy = get_noisy_kinematics(t)
    return struct.pack("6f", x_noisy, y_noisy, vx_noisy, vy_noisy, ax_noisy, ay_noisy)


def get_noisy_altitude(t: float) -> float:
    alt = get_altitude(t)
    cov = NOISE_COVARIANCES["altitude"]
    alt_noisy = add_noise(alt, math.sqrt(cov["altitude"]))
    return alt_noisy


def serialize_altitude(t: float) -> bytes:
    alt_noisy = get_noisy_altitude(t)
    return struct.pack("f", alt_noisy)


def get_noisy_gyro(t: float) -> tuple[float, float, float]:
    omega_x, omega_y, omega_z = get_angular_velocity(t)
    cov = NOISE_COVARIANCES["gyro"]
    omega_x_noisy = add_noise(omega_x, math.sqrt(cov["omega_x"]))
    omega_y_noisy = add_noise(omega_y, math.sqrt(cov["omega_y"]))
    omega_z_noisy = add_noise(omega_z, math.sqrt(cov["omega_z"]))
    return omega_x_noisy, omega_y_noisy, omega_z_noisy


def serialize_gyro(t: float) -> bytes:
    omega_x_noisy, omega_y_noisy, omega_z_noisy = get_noisy_gyro(t)
    return struct.pack("3f", omega_x_noisy, omega_y_noisy, omega_z_noisy)


def main():
    print(f"Broadcasting {broadcast_type} data")
    print(f"Flight time: {FLIGHT_TIME:.2f}s, Max altitude: {MAX_ALTITUDE:.2f}m")

    session = zenoh.open(zenoh.Config())

    start_time = time.time()

    while True:
        elapsed = time.time() - start_time

        if elapsed > FLIGHT_TIME:
            print("Trajectory complete. Stopping.")
            break

        if broadcast_type == "kinematics":
            x_noisy, y_noisy, vx_noisy, vy_noisy, ax_noisy, ay_noisy = (
                get_noisy_kinematics(elapsed)
            )
            data = struct.pack(
                "6f", x_noisy, y_noisy, vx_noisy, vy_noisy, ax_noisy, ay_noisy
            )
            print(
                f"t={elapsed:.2f}s: pos=({x_noisy:.2f}, {y_noisy:.2f})m, vel=({vx_noisy:.2f}, {vy_noisy:.2f})m/s"
            )
        elif broadcast_type == "altitude":
            alt_noisy = get_noisy_altitude(elapsed)
            data = struct.pack("f", alt_noisy)
            print(f"t={elapsed:.2f}s: altitude={alt_noisy:.2f}m")
        elif broadcast_type == "gyro":
            omega_x_noisy, omega_y_noisy, omega_z_noisy = get_noisy_gyro(elapsed)
            data = struct.pack("3f", omega_x_noisy, omega_y_noisy, omega_z_noisy)
            print(
                f"t={elapsed:.2f}s: ω=({omega_x_noisy:.2f}, {omega_y_noisy:.2f}, {omega_z_noisy:.2f})rad/s"
            )
        else:
            print(f"Unknown broadcast type: {broadcast_type}")
            break

        session.put(f"devices/{broadcast_type}", data)
        time.sleep(0.1)

    session.close()


if __name__ == "__main__":
    main()
