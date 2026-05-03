use ipc_vsock::client::AuthCarrier;
use proto::crossdesk::v1::filesystem_service_client::FilesystemServiceClient;
use proto::crossdesk::v1::{ShareGuestFrame, share_guest_frame::Payload};
use tokio::sync::mpsc;
use tokio::task::JoinSet;
use tokio_stream::wrappers::ReceiverStream;
use tracing::{debug, error, info};

pub async fn run_filesystem_channel(
    mut client: FilesystemServiceClient<tonic::transport::Channel>,
    auth: AuthCarrier,
) -> Result<(), anyhow::Error> {
    info!("Starting Filesystem JIT Service");

    let (tx, rx) = mpsc::channel::<ShareGuestFrame>(32);

    let response_stream = client
        .share_channel(ReceiverStream::new(rx))
        .await?
        .into_inner();
    let mut host_stream = response_stream;

    // JoinSet owns every per-mount worker; dropping it cancels them in one
    // place when the host stream goes away. The previous version detached
    // the workers with bare `tokio::spawn` and they outlived the channel,
    // which leaked tasks every time the host disconnected mid-mount.
    let mut workers: JoinSet<()> = JoinSet::new();

    while let Some(msg_result) = host_stream.message().await.transpose() {
        let host_frame = match msg_result {
            Ok(f) => f,
            Err(e) => {
                error!("Filesystem stream error: {:?}", e);
                break;
            }
        };

        let Some(payload) = host_frame.payload else { continue };
        match payload {
            proto::crossdesk::v1::share_host_frame::Payload::Mount(req) => {
                info!(
                    focal = %req.focal_filename,
                    share = %req.share_id,
                    "Received MountRequest",
                );
                let idle_duration = req
                    .idle_release_after
                    .map(|d| std::time::Duration::from_secs(d.seconds as u64))
                    .unwrap_or(std::time::Duration::from_secs(5));

                let mount_result = fs_mount::mount::mock_handle_mount_request(
                    &req.share_id,
                    &req.guest_drive_letter,
                    &req.mount_token,
                )
                .await;

                let out_frame = ShareGuestFrame {
                    auth: Some(auth.next()),
                    sent_at: None,
                    payload: Some(Payload::MountResult(mount_result)),
                };
                if tx.send(out_frame).await.is_err() {
                    error!("Failed to send MountResult");
                    break;
                }

                let tx_for_worker = tx.clone();
                let auth_for_worker = auth.clone();
                let share_id = req.share_id;
                let token = req.mount_token;
                workers.spawn(async move {
                    tokio::time::sleep(idle_duration).await;

                    let report =
                        fs_mount::flush::mock_generate_lock_report(&share_id, &token).await;
                    if tx_for_worker
                        .send(ShareGuestFrame {
                            auth: Some(auth_for_worker.next()),
                            sent_at: None,
                            payload: Some(Payload::LockReport(report)),
                        })
                        .await
                        .is_err()
                    {
                        return;
                    }

                    tokio::time::sleep(std::time::Duration::from_secs(1)).await;
                    let ack =
                        fs_mount::flush::mock_generate_release_ack(&share_id, &token).await;
                    if tx_for_worker
                        .send(ShareGuestFrame {
                            auth: Some(auth_for_worker.next()),
                            sent_at: None,
                            payload: Some(Payload::ReleaseAck(ack)),
                        })
                        .await
                        .is_ok()
                    {
                        info!(share = %share_id, "ReleaseAck sent");
                    }
                });
            }
            proto::crossdesk::v1::share_host_frame::Payload::Detach(req) => {
                info!(share = %req.share_id, "Received DetachRequest");
            }
            proto::crossdesk::v1::share_host_frame::Payload::LockQuery(req) => {
                debug!(share = %req.share_id, "Received LockQuery");
            }
        }
    }

    info!("Filesystem channel disconnected; aborting in-flight workers");
    workers.abort_all();
    while workers.join_next().await.is_some() {}

    Ok(())
}
