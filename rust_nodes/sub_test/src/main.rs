use zenoh_ext::z_deserialize;

#[tokio::main]
async fn main() {
    let session = zenoh::open(zenoh::Config::default())
        .await
        .expect("Failed to open Zenoh session.");

    let subscriber = session
        .declare_subscriber("devices/temp")
        .await
        .expect("Failed to declare subscriber.");

    while let Ok(sample) = subscriber.recv_async().await {
        let load = sample.payload();
        println!("Raw payload: {:?}", load);

        let sample: f32 = match z_deserialize(load) {
            Ok(value) => value,
            Err(e) => {
                eprintln!("Deserialization error: {}", e);
                continue;
            }
        };

        println!("Received: {:?}", sample);
    }
}
