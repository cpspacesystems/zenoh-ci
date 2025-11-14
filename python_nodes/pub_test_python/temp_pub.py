#!/usr/bin/env python3

import time
import random
import struct
import zenoh


def read_temp():
    return random.uniform(0.0, 100.0)


def main():
    session = zenoh.open(zenoh.Config())

    while True:
        temp = read_temp()
        serialized_temp = struct.pack("f", temp)
        deserialized_temp = struct.unpack("f", serialized_temp)[0]
        print(f"Deserialized temperature: {deserialized_temp:.2f}")
        session.put("devices/temp", serialized_temp)
        time.sleep(1)


if __name__ == "__main__":
    main()
