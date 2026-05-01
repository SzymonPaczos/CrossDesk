use std::time::{Instant, SystemTime, UNIX_EPOCH};
use tokio::sync::mpsc;
use tonic::Request;
use tracing::{info, debug, error};

use proto::crossdesk::v1::{
    heartbeat_service_client::HeartbeatServiceClient,
    GuestFrame, GuestState, Pong, ResourcePressure,
};
use proto::crossdesk::v1::guest_frame::Payload;

pub async fn run_heartbeat_loop(mut client: HeartbeatServiceClient<tonic::transport::Channel>) -> Result<(), anyhow::Error> {
    info!("Starting Heartbeat Loop");

    let (tx, rx) = mpsc::channel::<GuestFrame>(32);
    let request = Request::new(tokio_stream::wrappers::ReceiverStream::new(rx));
    
    // Inicjujemy asynchronicznie strumień z Hostem
    let mut response_stream = client.channel(request).await?.into_inner();
    let epoch_start = Instant::now();

    // Oczekujemy na ramki HostFrame (Ping / Directive)
    while let Some(msg_result) = response_stream.message().await.transpose() {
        match msg_result {
            Ok(host_frame) => {
                let recv_ns = epoch_start.elapsed().as_nanos() as u64;
                
                if let Some(proto::crossdesk::v1::host_frame::Payload::Ping(ping)) = host_frame.payload {
                    debug!("Received PING sequence: {}", ping.sequence);
                    
                    let send_ns = epoch_start.elapsed().as_nanos() as u64;
                    
                    let pong_frame = GuestFrame {
                        auth: None, // Obsługiwane przez interceptor Fazy 2
                        payload: Some(Payload::Pong(Pong {
                            sequence: ping.sequence,
                            host_send_monotonic_ns: ping.host_send_monotonic_ns,
                            guest_recv_monotonic_ns: recv_ns,
                            guest_send_monotonic_ns: send_ns,
                            state: GuestState::Ready.into(),
                            pressure: Some(ResourcePressure {
                                cpu_percent: 0,
                                memory_percent: 0,
                                disk_io_pressure: 0,
                            }),
                        })),
                    };
                    
                    if tx.send(pong_frame).await.is_err() {
                        error!("Failed to send PONG frame");
                        break;
                    }
                }
            }
            Err(e) => {
                error!("Heartbeat stream error: {:?}", e);
                break;
            }
        }
    }

    info!("Heartbeat loop ended.");
    Ok(())
}
