use rand::Rng;
use std::thread;
use std::time::Duration;
use tokio;
use zenoh;
use zenoh_ext::z_deserialize;
use zenoh_ext::z_serialize;

fn read_temp() -> f32 {
    let mut rng = rand::rng();
    rng.random_range(0.0..100.0)
}

#[tokio::main]
async fn main() {
    let session = zenoh::open(zenoh::Config::default()).await.unwrap();

    loop {
        let ftemp = read_temp();
        let ftemp = z_serialize(&ftemp);
        let deser_ftemp: f32 = z_deserialize(&ftemp).unwrap();
        println!("Deserialized temperature: {}", deser_ftemp);

        session
            .put("devices/temp", ftemp)
            .await
            .expect("failed to put data");

        thread::sleep(Duration::from_secs(1));
    }
}
