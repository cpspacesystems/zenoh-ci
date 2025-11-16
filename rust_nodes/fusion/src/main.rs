use futures::StreamExt;
use sensors_rs::sensors;
use std::thread::sleep;
use std::time::Duration;
use tokio;
use zenoh;
use zenoh::query::ConsolidationMode;

// 3 IMUs, 2 gyroscopes, 4 altimeters
const N_FLOATS: usize = 3 * 3 + 2 * 3 + 4 * 1;
const CLOCK_PER: u64 = 10; // ms
const IMU_KEYS: [&str; 3] = ["imu0", "imu1", "imu2"];
const GYRO_KEYS: [&str; 2] = ["gyro0", "gyro1"];
const ALT_KEYS: [&str; 4] = ["altitude0", "altitude1", "altitude2", "altitude3"];
const BASE_SENSOR_KEY: &str = "devices/";

async fn query_latest_value(session: &zenoh::Session, key: &str) -> Option<zenoh::sample::Sample> {
    let res = session
        .get(key)
        .consolidation(ConsolidationMode::Latest)
        .timeout(Duration::from_millis(50))
        .await;

    return match res {
        Ok(res) => match res.into_stream().next().await {
            Some(reply) => match reply.into_result() {
                Ok(sample) => Some(sample),
                Err(e) => {
                    eprintln!("Error in sample for key {}: {}", key, e);
                    None
                }
            },
            None => {
                eprintln!("No sample found for key {}", key);
                None
            }
        },
        Err(e) => {
            eprintln!("Error in query for key {}: {}", key, e);
            None
        }
    };
}

// Queries a list of sensor keys of homogeneous sensor type and parses the payloads
// into the measurement array at the given base index. Parsing and population in the
// measurement array is defined by the parser function.
async fn query_and_parse<F>(
    session: &zenoh::Session,
    keys: &[&str],
    measurement: &mut [f32],
    mut base: usize,
    stride: usize,
    parser: F,
) -> usize
where
    F: Fn(&[u8], &mut [f32], usize),
{
    for key in keys.iter() {
        let full_key = format!("{}{}", BASE_SENSOR_KEY, key);
        let sample = query_latest_value(session, &full_key).await;
        if let Some(sample) = sample {
            let payload = sample.payload().to_bytes();
            parser(&payload, measurement, base);
        }
        base += stride;
    }
    base
}

fn parse_imu(payload: &[u8], meas: &mut [f32], idx: usize) {
    if let Ok(imu_data) = flatbuffers::root::<sensors::IMU>(payload) {
        if let Some(accel) = imu_data.acceleration() {
            meas[idx] = accel.x();
            meas[idx + 1] = accel.y();
            meas[idx + 2] = accel.z();
        }
    }
}

fn parse_gyro(payload: &[u8], meas: &mut [f32], idx: usize) {
    if let Ok(gyro_data) = flatbuffers::root::<sensors::Gyro>(payload) {
        meas[idx] = gyro_data.omega_x();
        meas[idx + 1] = gyro_data.omega_y();
        meas[idx + 2] = gyro_data.omega_z();
    }
}

fn parse_altitude(payload: &[u8], meas: &mut [f32], idx: usize) {
    if let Ok(altitude_data) = flatbuffers::root::<sensors::Altitude>(payload) {
        meas[idx] = altitude_data.altitude();
    }
}

// Refreshes the measurement array with the latest values queried from the sensors.
async fn refresh_meas(session: &zenoh::Session, measurement: &mut [f32; N_FLOATS]) {
    let mut base = 0;

    base = query_and_parse(session, &IMU_KEYS, measurement, base, 3, parse_imu).await;
    base = query_and_parse(session, &GYRO_KEYS, measurement, base, 3, parse_gyro).await;
    query_and_parse(session, &ALT_KEYS, measurement, base, 1, parse_altitude).await;
}

fn echo_meas(measurement: &[f32; N_FLOATS]) {
    println!("{}", measurement.map(|x| format!("{:6.2}", x)).join(", "));
}

#[tokio::main]
async fn main() {
    let session = zenoh::open(zenoh::Config::default())
        .await
        .expect("Failed to open Zenoh session.");

    let mut measurement = [0.0_f32; N_FLOATS];
    loop {
        refresh_meas(&session, &mut measurement).await;
        echo_meas(&measurement);
        sleep(Duration::from_millis(CLOCK_PER));
    }
}
