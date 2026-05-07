#[cfg(windows)]
fn main() -> anyhow::Result<()> {
    agent_svc::service::start_service_dispatcher()?;
    Ok(())
}

#[cfg(not(windows))]
fn main() {
    eprintln!("CrossDeskAgent is a Windows NT service; it cannot run on this platform.");
    std::process::exit(1);
}
