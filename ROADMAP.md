Faza 1 — Bootstrap VM + NT Service
Fundament: qemu:///session + autounattend.xml + floppy inject
Dowód: headless instalacja Windows → agent.exe zarejestrowany jako NT service, uruchamia się przed user login, przeżywa reboot
SPOF: FirstLogonCommands → sc create — jeśli SCM cicho odrzuci binarkę (brak signed driver / ACL), wszystko wyżej jest niemożliwe do zdiagnozowania bez RDP
Faza 2 — Transport vsock + mTLS + AuthContext
Fundament: tonic gRPC nad AF_VSOCK z mTLS handshake
Dowód: bidirectional stream Host↔Guest, peer_cert_fingerprint + stream_nonce + sequence weryfikowane per-frame; celowa CID collision odrzucona
SPOF: enforcement AuthContext przed przetworzeniem payloadu — pojedyncza ścieżka kodu omijająca walidację = cały model zagrożeń runie
Faza 3 — Control Session FSM + Adaptive Heartbeat
Fundament: ControlService.OpenSession + HeartbeatService.Channel + FSM recovery
Dowód: AppLaunchRequest → AppLaunched → AppLifecycleEvent(EXITED); sztuczny stall Guesta przechodzi HEALTHY → DEGRADED → PROBING → SOFT_RECOVERY → HARD_DESTROY z exponential backoff
SPOF: tuning EWMA RTT + miss_threshold — false-positive HARD_DESTROY = virsh destroy w trakcie pracy użytkownika (utrata danych); false-negative = zawieszona sesja bez recovery
Faza 4 — RAIL Display Integration
Fundament: RailWindowEvent → FreeRDP RAIL spawn → natywne okno Wayland/X11
Dowód: CREATED event z Guesta produkuje okno w compositorze Linux z poprawną geometrią/tytułem/ikoną; DESTROYED czyści bez leaku
SPOF: kolejność i idempotencja eventów (CREATED przed FOCUS_GAINED, brak zgubionego DESTROYED) — rozjazd stanu HWND↔Linux window = ghost windows lub orphaned process
Faza 5 — JIT VirtioFS + ReleaseAck Protocol
Fundament: minimal-path share → libvirt hot-plug → Guest mount → ReleaseAck → detach
Dowód: kliknięcie pliku w Linux → share widoczny tylko dla tego procesu → zamknięcie app → LockReport (0 handles) → ReleaseAck → virsh detach-device; path traversal blokowany
SPOF: handshake ReleaseAck — detach przed flushem = corrupt write; brak ReleaseAck = permanentny leak share'a (łamie inwariant "NIE permanentny mount")