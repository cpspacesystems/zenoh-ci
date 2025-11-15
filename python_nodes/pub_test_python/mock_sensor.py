#!/usr/bin/env python3

import time
import sys
import zenoh
import os
import math
import numpy as np
from typing import Literal
import flatbuffers

sys.path.append(os.path.join(os.path.dirname(__file__), "../../types"))
from schemas.sensors import Kinematics, Altitude, Gyro, Vec3

broadcast_type: Literal[
    "kinematics",
    "gyro",
    "altitude",
] = os.environ.get("DUMMY_BROADCAST_TYPE", "kinematics")

INITIAL_VELOCITY = 100.0
GRAVITY = 9.81
LAUNCH_ANGLE = math.radians(75)
AZIMUTH_ANGLE = math.radians(30)

V0_X = INITIAL_VELOCITY * math.cos(LAUNCH_ANGLE) * math.cos(AZIMUTH_ANGLE)
V0_Y = INITIAL_VELOCITY * math.cos(LAUNCH_ANGLE) * math.sin(AZIMUTH_ANGLE)
V0_Z = INITIAL_VELOCITY * math.sin(LAUNCH_ANGLE)

FLIGHT_TIME = 2 * V0_Z / GRAVITY
MAX_ALTITUDE = (V0_Z**2) / (2 * GRAVITY)

NOISE_COVARIANCES = {
    "kinematics": {
        "position_x": 100,
        "position_y": 100,
        "position_z": 100,
        "velocity_x": 100,
        "velocity_y": 100,
        "velocity_z": 100,
        "acceleration_x": 100,
        "acceleration_y": 100,
        "acceleration_z": 100,
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


def get_position(t: float) -> tuple[float, float, float]:
    x = V0_X * t
    y = V0_Y * t
    z = V0_Z * t - 0.5 * GRAVITY * t * t
    return x, y, z


def get_velocity(t: float) -> tuple[float, float, float]:
    vx = V0_X
    vy = V0_Y
    vz = V0_Z - GRAVITY * t
    return vx, vy, vz


def get_altitude(t: float) -> float:
    return V0_Z * t - 0.5 * GRAVITY * t * t


def get_acceleration(t: float) -> tuple[float, float, float]:
    return 0.0, 0.0, -GRAVITY


def get_angular_velocity(t: float) -> tuple[float, float, float]:
    phase = t * 2 * math.pi / FLIGHT_TIME
    omega_x = 0.5 * math.sin(phase)
    omega_y = 0.3 * math.cos(phase * 1.5)
    omega_z = 0.8 * math.sin(phase * 0.7)
    return omega_x, omega_y, omega_z


def add_noise(value: float, std_dev: float) -> float:
    return value + np.random.normal(0, std_dev)


def get_noisy_kinematics(
    t: float,
) -> tuple[float, float, float, float, float, float, float, float, float]:
    x, y, z = get_position(t)
    vx, vy, vz = get_velocity(t)
    ax, ay, az = get_acceleration(t)

    cov = NOISE_COVARIANCES["kinematics"]
    x_noisy = add_noise(x, math.sqrt(cov["position_x"]))
    y_noisy = add_noise(y, math.sqrt(cov["position_y"]))
    z_noisy = add_noise(z, math.sqrt(cov["position_z"]))
    vx_noisy = add_noise(vx, math.sqrt(cov["velocity_x"]))
    vy_noisy = add_noise(vy, math.sqrt(cov["velocity_y"]))
    vz_noisy = add_noise(vz, math.sqrt(cov["velocity_z"]))
    ax_noisy = add_noise(ax, math.sqrt(cov["acceleration_x"]))
    ay_noisy = add_noise(ay, math.sqrt(cov["acceleration_y"]))
    az_noisy = add_noise(az, math.sqrt(cov["acceleration_z"]))

    return (
        x_noisy,
        y_noisy,
        z_noisy,
        vx_noisy,
        vy_noisy,
        vz_noisy,
        ax_noisy,
        ay_noisy,
        az_noisy,
    )


def serialize_kinematics(t: float) -> bytes:
    (
        x_noisy,
        y_noisy,
        z_noisy,
        vx_noisy,
        vy_noisy,
        vz_noisy,
        ax_noisy,
        ay_noisy,
        az_noisy,
    ) = get_noisy_kinematics(t)

    builder = flatbuffers.Builder(256)

    Kinematics.Start(builder)
    Kinematics.AddPosition(
        builder,
        Vec3.CreateVec3(builder, x_noisy, y_noisy, z_noisy),
    )
    Kinematics.AddVelocity(
        builder,
        Vec3.CreateVec3(builder, vx_noisy, vy_noisy, vz_noisy),
    )
    Kinematics.AddAcceleration(
        builder,
        Vec3.CreateVec3(builder, ax_noisy, ay_noisy, az_noisy),
    )
    kinematics = Kinematics.End(builder)

    builder.Finish(kinematics)
    return bytes(builder.Output())


def get_noisy_altitude(t: float) -> float:
    alt = get_altitude(t)
    cov = NOISE_COVARIANCES["altitude"]
    alt_noisy = add_noise(alt, math.sqrt(cov["altitude"]))
    return alt_noisy


def serialize_altitude(t: float) -> bytes:
    alt_noisy = get_noisy_altitude(t)

    builder = flatbuffers.Builder(64)

    Altitude.Start(builder)
    Altitude.AddAltitude(builder, alt_noisy)
    altitude = Altitude.End(builder)

    builder.Finish(altitude)
    return bytes(builder.Output())


def get_noisy_gyro(t: float) -> tuple[float, float, float]:
    omega_x, omega_y, omega_z = get_angular_velocity(t)
    cov = NOISE_COVARIANCES["gyro"]
    omega_x_noisy = add_noise(omega_x, math.sqrt(cov["omega_x"]))
    omega_y_noisy = add_noise(omega_y, math.sqrt(cov["omega_y"]))
    omega_z_noisy = add_noise(omega_z, math.sqrt(cov["omega_z"]))
    return omega_x_noisy, omega_y_noisy, omega_z_noisy


def serialize_gyro(t: float) -> bytes:
    omega_x_noisy, omega_y_noisy, omega_z_noisy = get_noisy_gyro(t)

    builder = flatbuffers.Builder(64)

    Gyro.Start(builder)
    Gyro.AddOmegaX(builder, omega_x_noisy)
    Gyro.AddOmegaY(builder, omega_y_noisy)
    Gyro.AddOmegaZ(builder, omega_z_noisy)
    gyro = Gyro.End(builder)

    builder.Finish(gyro)
    return bytes(builder.Output())


def main():
    print(f"Starting query-based {broadcast_type} sensor")
    print(f"Flight time: {FLIGHT_TIME:.2f}s, Max altitude: {MAX_ALTITUDE:.2f}m")

    session = zenoh.open(zenoh.Config())
    start_time = time.time()

    def query_handler(query):
        elapsed = time.time() - start_time

        if elapsed > FLIGHT_TIME:
            print(f"Query received after trajectory completion (t={elapsed:.2f}s)")
            query.reply(f"devices/{broadcast_type}", b"")
            return

        match broadcast_type:
            case "kinematics":
                data = serialize_kinematics(elapsed)
            case "altitude":
                data = serialize_altitude(elapsed)
            case "gyro":
                data = serialize_gyro(elapsed)
            case _:
                print(f"Unknown broadcast type: {broadcast_type}")
                query.reply(f"devices/{broadcast_type}", b"")
                return

        query.reply(f"devices/{broadcast_type}", data)
        print(f"Query @ t={elapsed:.2f}s: {data}")

    queryable = session.declare_queryable(f"devices/{broadcast_type}", query_handler)

    print(f"Queryable declared on 'devices/{broadcast_type}'")
    print("Ready to respond to queries. Press Ctrl-C to exit.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        queryable.undeclare()
        session.close()


if __name__ == "__main__":
    main()
