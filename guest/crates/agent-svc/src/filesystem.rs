use proto::crossdesk::v1::filesystem_service_client::FilesystemServiceClient;
use proto::crossdesk::v1::{ShareGuestFrame, share_guest_frame::Payload};
use tokio::sync::mpsc;
use tracing::{info, error, debug};
use tokio_stream::wrappers::ReceiverStream;

pub async fn run_filesystem_channel(mut client: FilesystemServiceClient<tonic::transport::Channel>) -> Result<(), anyhow::Error> {
    info!("Starting Filesystem JIT Service");

    let (tx, rx) = mpsc::channel::<ShareGuestFrame>(32);

    // Wysyłamy strumień ramek Gościa do Hosta, otrzymując strumień od Hosta.
    let response_stream = client.share_channel(ReceiverStream::new(rx)).await?.into_inner();

    let mut host_stream = response_stream;
    
    // Pętla odczytu komend od Hosta
    while let Ok(Some(host_frame)) = host_stream.message().await {
        if let Some(payload) = host_frame.payload {
            match payload {
                proto::crossdesk::v1::share_host_frame::Payload::Mount(req) => {
                    info!("Received MountRequest for focal file: {}", req.focal_filename);
                    let share_id = req.share_id.clone();
                    let token = req.mount_token.clone();
                    let idle_duration = req.idle_release_after.map(|d| std::time::Duration::from_secs(d.seconds as u64)).unwrap_or(std::time::Duration::from_secs(5));
                    
                    let result = fs_mount::mount::handle_mount_request(&req.share_id, &req.guest_drive_letter, &req.mount_token).await;
                    
                    // Odpowiedź o wyniku
                    let out_frame = ShareGuestFrame {
                        auth: None, // zostanie wstrzyknięte przez interceptor
                        sent_at: None,
                        payload: Some(Payload::MountResult(result)),
                    };
                    
                    if tx.send(out_frame).await.is_err() {
                        error!("Failed to send MountResult");
                        break;
                    }
                    
                    // Uruchamiamy w tle pętlę generującą LockReport i ostatecznie ReleaseAck
                    let tx_clone = tx.clone();
                    tokio::spawn(async move {
                        // Polling flush
                        tokio::time::sleep(idle_duration).await;
                        
                        let report = fs_mount::flush::generate_mock_lock_report(&share_id, &token).await;
                        let _ = tx_clone.send(ShareGuestFrame {
                            auth: None,
                            sent_at: None,
                            payload: Some(Payload::LockReport(report)),
                        }).await;
                        
                        // Po raporcie, symulujemy pomyślny flush i zwalniamy
                        tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;
                        let ack = fs_mount::flush::generate_release_ack(&share_id, &token).await;
                        let _ = tx_clone.send(ShareGuestFrame {
                            auth: None,
                            sent_at: None,
                            payload: Some(Payload::ReleaseAck(ack)),
                        }).await;
                        
                        info!("ReleaseAck sent for share {}", share_id);
                    });
                },
                proto::crossdesk::v1::share_host_frame::Payload::Detach(req) => {
                    info!("Received DetachRequest for share {}", req.share_id);
                    // Prawdziwa implementacja potwierdza wymuszenie odpięcia.
                },
                proto::crossdesk::v1::share_host_frame::Payload::LockQuery(req) => {
                    debug!("Received LockQuery for share {}", req.share_id);
                }
            }
        }
    }

    info!("Filesystem channel disconnected");
    Ok(())
}
