import logging

logger = logging.getLogger(__name__)

class LibvirtControllerMock:
    """
    Zaślepka do integracji z libvirt. Realizuje akcje naprawcze logując je na ekran, 
    bez faktycznego niszczenia maszyn wirtualnych w trakcie prac deweloperskich.
    """
    def __init__(self, domain_name: str = "windows-guest"):
        self.domain_name = domain_name
        
    def hard_destroy(self) -> None:
        logger.critical(f"[LIBVIRT MOCK] Executing 'virsh destroy {self.domain_name}'!")
        logger.critical(f"[LIBVIRT MOCK] Executing 'virsh start {self.domain_name}'!")

    def graceful_shutdown(self) -> None:
        logger.warning(f"[LIBVIRT MOCK] Executing 'virsh shutdown {self.domain_name}'")
