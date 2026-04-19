#[cfg(windows)]
use {
    agent_svc::service::{ffi_service_main, SERVICE_NAME},
    windows_service::service_dispatcher,
};

#[cfg(windows)]
fn main() -> anyhow::Result<()> {
    service_dispatcher::start(SERVICE_NAME, ffi_service_main)?;
    Ok(())
}

#[cfg(not(windows))]
fn main() {
    eprintln!("CrossDeskAgent is a Windows NT service; it cannot run on this platform.");
    std::process::exit(1);
}
