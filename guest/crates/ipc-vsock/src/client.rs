use std::sync::{Arc, Mutex};
use tonic::transport::{Channel, ClientTlsConfig, Certificate, Identity};
use tonic::{Request, Status};
use rand::RngCore;

// Zakładamy, że wygenerowaliśmy strukturę AuthContext
use proto::crossdesk::v1::AuthContext;

#[derive(Clone)]
pub struct AuthInterceptor {
    peer_cert_fingerprint: String,
    stream_nonce: Vec<u8>,
    sequence: Arc<Mutex<u64>>,
}

impl AuthInterceptor {
    pub fn new(peer_cert_fingerprint: String) -> Self {
        let mut nonce = vec![0u8; 16];
        rand::thread_rng().fill_bytes(&mut nonce);
        
        Self {
            peer_cert_fingerprint,
            stream_nonce: nonce,
            sequence: Arc::new(Mutex::new(0)),
        }
    }
}

impl tonic::service::Interceptor for AuthInterceptor {
    fn call(&mut self, mut request: Request<()>) -> Result<Request<()>, Status> {
        // W gRPC interceptorach Rusta (Tonic) zwykle wstrzykujemy metadane do nagłówków.
        // Jeśli AuthContext jest wymagany jako część wiadomości w protobufie (zgodnie z common.proto),
        // musimy go wstawiać ręcznie w wywołaniach klientów,
        // ALBO serializować AuthContext do nagłówka (gRPC metadata) jeśli architektura na to pozwala.
        // Zakładając podejście z nagłówkami dla czystości logiki bizesowej:
        
        let mut seq = self.sequence.lock().unwrap();
        *seq += 1;
        
        // Możemy wstrzyknąć do nagłówków, a Host go zdekoduje
        request.metadata_mut().insert(
            "x-auth-fingerprint",
            self.peer_cert_fingerprint.parse().unwrap()
        );
        request.metadata_mut().insert(
            "x-auth-nonce",
            hex::encode(&self.stream_nonce).parse().unwrap()
        );
        request.metadata_mut().insert(
            "x-auth-sequence",
            seq.to_string().parse().unwrap()
        );

        Ok(request)
    }
}

pub async fn create_secure_channel(
    ca_cert_pem: &[u8],
    guest_cert_pem: &[u8],
    guest_key_pem: &[u8],
    host_fingerprint: String,
) -> Result<Channel, anyhow::Error> {
    let ca = Certificate::from_pem(ca_cert_pem);
    let identity = Identity::from_pem(guest_cert_pem, guest_key_pem);

    let tls = ClientTlsConfig::new()
        .ca_certificate(ca)
        .identity(identity)
        // Oczekiwana domena hosta certyfikatu
        .domain_name("CrossDesk Host");

    // Tymczasowy endpoint lokalny (do zastąpienia przez connector)
    let channel = Channel::from_static("http://[::1]:50051")
        .tls_config(tls)?
        .connect()
        .await?;

    Ok(channel)
}
