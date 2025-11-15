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
from schemas.sensors import IMU, Altitude, Gyro, Vec3

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
from covariances import NOISE_COVARIANCES

broadcast_type: Literal[
    "imu",
    "gyro",
    "altitude",
] = os.environ.get("DUMMY_BROADCAST_TYPE", "imu")

sensor_id: str = os.environ.get("SENSOR_ID", "0")

INITIAL_VELOCITY = 100.0
GRAVITY = 9.81
LAUNCH_ANGLE = math.radians(75)
AZIMUTH_ANGLE = math.radians(30)

V0_X = INITIAL_VELOCITY * math.cos(LAUNCH_ANGLE) * math.cos(AZIMUTH_ANGLE)
V0_Y = INITIAL_VELOCITY * math.cos(LAUNCH_ANGLE) * math.sin(AZIMUTH_ANGLE)
V0_Z = INITIAL_VELOCITY * math.sin(LAUNCH_ANGLE)

FLIGHT_TIME = 2 * V0_Z / GRAVITY
MAX_ALTITUDE = (V0_Z**2) / (2 * GRAVITY)

launch_started = False
launch_time = None


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


def get_noisy_imu(
    t: float,
) -> tuple[float, float, float]:
    cov = NOISE_COVARIANCES["imu"]

    if not launch_started:
        ax_noisy = add_noise(0.0, math.sqrt(cov["acceleration_x"]))
        ay_noisy = add_noise(0.0, math.sqrt(cov["acceleration_y"]))
        az_noisy = add_noise(0.0, math.sqrt(cov["acceleration_z"]))
        return (ax_noisy, ay_noisy, az_noisy)

    ax, ay, az = get_acceleration(t)
    ax_noisy = add_noise(ax, math.sqrt(cov["acceleration_x"]))
    ay_noisy = add_noise(ay, math.sqrt(cov["acceleration_y"]))
    az_noisy = add_noise(az, math.sqrt(cov["acceleration_z"]))

    return (
        ax_noisy,
        ay_noisy,
        az_noisy,
    )


def serialize_imu(t: float) -> bytes:
    (
        ax_noisy,
        ay_noisy,
        az_noisy,
    ) = get_noisy_imu(t)

    builder = flatbuffers.Builder(256)

    IMU.Start(builder)
    IMU.AddAcceleration(
        builder,
        Vec3.CreateVec3(builder, ax_noisy, ay_noisy, az_noisy),
    )
    imu = IMU.End(builder)

    builder.Finish(imu)
    return bytes(builder.Output())


def get_noisy_altitude(t: float) -> float:
    cov = NOISE_COVARIANCES["altitude"]

    if not launch_started:
        alt_noisy = add_noise(0.0, math.sqrt(cov["altitude"]))
        return alt_noisy

    alt = get_altitude(t)
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
    cov = NOISE_COVARIANCES["gyro"]

    if not launch_started:
        omega_x_noisy = add_noise(0.0, math.sqrt(cov["omega_x"]))
        omega_y_noisy = add_noise(0.0, math.sqrt(cov["omega_y"]))
        omega_z_noisy = add_noise(0.0, math.sqrt(cov["omega_z"]))
        return omega_x_noisy, omega_y_noisy, omega_z_noisy

    omega_x, omega_y, omega_z = get_angular_velocity(t)
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
    target_topic = f"devices/{broadcast_type}_{sensor_id}"
    launch_topic = "launch"

    def launch_handler(sample):
        global launch_started, launch_time
        message = sample.payload.to_string()
        if message == "s":
            launch_started = True
            launch_time = time.time()
            print(f"Launch sequence initiated at t={launch_time:.2f}")

    def query_handler(query):
        if not launch_started or launch_time is None:
            elapsed = 0.0
        else:
            elapsed = time.time() - launch_time
            if elapsed > FLIGHT_TIME:
                print(f"Query received after trajectory completion (t={elapsed:.2f}s)")
                query.reply(target_topic, b"")
                return

        match broadcast_type:
            case "imu":
                data = serialize_imu(elapsed)
            case "altitude":
                data = serialize_altitude(elapsed)
            case "gyro":
                data = serialize_gyro(elapsed)
            case _:
                print(f"Unknown broadcast type: {broadcast_type}")
                query.reply(target_topic, b"")
                return

        query.reply(target_topic, data)
        print(f"Query @ t={elapsed:.2f}s: {data}")

    subscriber = session.declare_subscriber(launch_topic, launch_handler)
    queryable = session.declare_queryable(target_topic, query_handler)

    print(f"Subscribed to launch topic '{launch_topic}'")
    print(f"Queryable declared on '{target_topic}'")
    print("Waiting for launch command. Press Ctrl-C to exit.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        subscriber.undeclare()
        queryable.undeclare()
        session.close()


if __name__ == "__main__":
    main()
