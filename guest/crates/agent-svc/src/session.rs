use tokio::sync::mpsc;
use tonic::Request;
use tracing::{info, warn, error};

use ipc_vsock::client::AuthCarrier;
use proto::crossdesk::v1::{
    control_service_client::ControlServiceClient,
    ClientFrame, ClientHello, ServerFrame,
};
use proto::crossdesk::v1::client_frame::Payload;

use crate::host_uuid::read_host_domain_uuid;

pub async fn run_control_session<T>(
    mut client: ControlServiceClient<T>,
    auth: AuthCarrier,
) -> Result<(), anyhow::Error>
where
    T: tonic::client::GrpcService<tonic::body::BoxBody>,
    T::Error: Into<tonic::codegen::StdError>,
    T::ResponseBody: tonic::codegen::Body<Data = tonic::codegen::Bytes> + Send + 'static,
    <T::ResponseBody as tonic::codegen::Body>::Error: Into<tonic::codegen::StdError> + Send,
{
    info!("Starting Control Session FSM");

    let host_domain_uuid = read_host_domain_uuid()?;
    info!(uuid = %host_domain_uuid, "Resolved host domain UUID");

    let (tx, rx) = mpsc::channel::<ClientFrame>(32);

    let (rail_tx, mut rail_rx) = mpsc::channel(64);
    rail_bridge::start_hook_thread(rail_tx);

    let tx_clone = tx.clone();
    let auth_for_rail = auth.clone();
    tokio::spawn(async move {
        while let Some(rail_event) = rail_rx.recv().await {
            let frame = ClientFrame {
                auth: Some(auth_for_rail.next()),
                sent_at: None,
                payload: Some(Payload::RailEvent(rail_event)),
            };
            if tx_clone.send(frame).await.is_err() {
                break;
            }
        }
    });

    let hello_frame = ClientFrame {
        auth: Some(auth.next()),
        sent_at: None,
        payload: Some(Payload::Hello(ClientHello {
            host_version: "0.1.0".to_string(),
            supported_features: vec!["rail.v1".to_string()],
            host_domain_uuid,
        })),
    };

    if tx.send(hello_frame).await.is_err() {
        return Err(anyhow::anyhow!("Failed to send ClientHello"));
    }

    let request = Request::new(tokio_stream::wrappers::ReceiverStream::new(rx));
    let mut response_stream = client.open_session(request).await?.into_inner();

    // Pętla nasłuchująca na odpowiedzi z serwera
    while let Some(msg_result) = response_stream.message().await.transpose() {
        match msg_result {
            Ok(server_frame) => {
                handle_server_frame(server_frame);
            }
            Err(e) => {
                error!("Control Session stream error: {:?}", e);
                break;
            }
        }
    }

    info!("Control Session stream ended.");
    Ok(())
}

fn handle_server_frame(frame: ServerFrame) {
    if let Some(payload) = frame.payload {
        match payload {
            proto::crossdesk::v1::server_frame::Payload::Accept(accept) => {
                info!("Server Accepted session: {:?}", accept.negotiated_features);
            }
            proto::crossdesk::v1::server_frame::Payload::AuthFailure(err) => {
                error!("Auth Failure: {:?}", err);
            }
            proto::crossdesk::v1::server_frame::Payload::Launched(launched) => {
                info!("App Launched, PID: {}", launched.process_id);
            }
            _ => {
                warn!("Unhandled ServerFrame payload");
            }
        }
    }
}
