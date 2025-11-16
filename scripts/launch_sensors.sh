#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

PIDS=()

cleanup() {
    echo "Shutting down all sensor nodes..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null
    done
    wait
    echo "All sensor nodes stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "Building mock_sensor..."
bazel build //python_nodes/pub_test_python:mock_sensor

if [ $? -ne 0 ]; then
    echo "Build failed!"
    exit 1
fi

MOCK_SENSOR_BIN="$PROJECT_ROOT/bazel-bin/python_nodes/pub_test_python/mock_sensor"

echo "Launching sensor nodes..."

for i in {0..2}; do
    DUMMY_BROADCAST_TYPE=imu SENSOR_ID=$i "$MOCK_SENSOR_BIN" &
    PIDS+=($!)
    echo "Started IMU sensor $i (PID: ${PIDS[-1]})"
done

for i in {0..1}; do
    DUMMY_BROADCAST_TYPE=gyro SENSOR_ID=$i "$MOCK_SENSOR_BIN" &
    PIDS+=($!)
    echo "Started gyro sensor $i (PID: ${PIDS[-1]})"
done

for i in {0..3}; do
    DUMMY_BROADCAST_TYPE=altitude SENSOR_ID=$i "$MOCK_SENSOR_BIN" &
    PIDS+=($!)
    echo "Started altimeter sensor $i (PID: ${PIDS[-1]})"
done

echo "All sensor nodes launched!"
echo "Press Ctrl-C to stop all nodes."

wait

