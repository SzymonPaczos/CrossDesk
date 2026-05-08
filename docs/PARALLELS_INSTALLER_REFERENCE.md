# Parallels Desktop Installer — UX Reference for CrossDesk

Purpose: capture the end-to-end UX of Parallels Desktop for Mac (the
.app installer plus the in-app first-run wizard that bootstraps a guest
OS) so CrossDesk can deliberately borrow what works and avoid what
doesn't. Parallels is the closest commercial analogue to CrossDesk's
"Windows-apps-as-native-Linux-windows" pitch — they have spent two
decades polishing the on-ramp for non-technical users, and the wizard
shown in this recording reflects most of that accumulated polish.

Source material: a 22-minute screen recording of a clean Parallels
Desktop install on Apple Silicon macOS, locale `pl_PL`, taken in 2024-11
(trial expiry shown is `10.11.2024`, EULA last-updated `kwiecień 2024`).
267 JPG frames were extracted at scene-change threshold 0.04 + a 15s
periodic sample. Frames live at `frames/f_NNNN.jpg` and are gitignored —
this document refers to them by number only (e.g. `f_0040`). All
on-screen Polish strings below are quoted in italics and translated.

---

## 1. Executive summary

Parallels Desktop's first-run UX is a 22-minute, two-stage funnel:

1. **Install the .app** (download → EULA → telemetry opt-in → folder
   permission grants → an Apple authentication challenge).
2. **First-run wizard** that is essentially a single screen — *"Utwórz
   nowy"* / "Create new" — offering eight install paths (Windows-from-
   Microsoft, custom ISO, and six prepackaged OS downloads), then
   driving the user through Microsoft's own ISO download, an automatic
   Windows-Setup run, OOBE, Windows EULA, and finally a Parallels
   account/license prompt before handing over to the guest desktop.

The flow is striking for two reasons. First, it *defaults to a fully
automated Windows-11 install* — the user clicks one tile and the
wizard does the ISO download, the Windows installer, OOBE, and post-
install glue without a single further prompt. Second, it *front-loads
all consent/permission prompts before any productive work*, so the
"installation" is over before Windows boots. Neither of these is free —
both are quite friction-heavy in absolute terms — but they are the
right choices.

| # | Phase | Frame range | What happens |
|---|---|---|---|
| 1 | Disk-image splash | `f_0001..f_0007` | DMG mount, "Instalacja oprogramowania Parallels Desktop" launcher |
| 2 | EULA acceptance | `f_0008..f_0009` | Polish EULA modal, *Odrzuć* / *Akceptuj* |
| 3 | Telemetry opt-in | `f_0010..f_0011` | "Program Parallels Customer Experience", *Wyłącz* / *Włącz* |
| 4 | Download / init | `f_0012..f_0019` | 193 MB download, "Inicjalizacja Parallels Desktop…" |
| 5 | Touch ID / password gate | `f_0014..f_0016` | macOS authentication prompt, *Anuluj* / *Użyj hasła…* |
| 6 | App launch into permission wizard | `f_0022..f_0034` | "Uprawnienia oprogramowania Parallels Desktop" + 3 macOS folder-access dialogs |
| 7 | OS chooser ("Utwórz nowy") | `f_0040..f_0073` | Single screen with two main tiles + horizontal carousel of free OSes |
| 8 | Windows-from-Microsoft confirmation | `f_0037`, `f_0080..f_0082` | "Pobierz i zainstaluj system Windows 11" splash, *Inne opcje…* / *Zainstaluj Windows* |
| 9 | Windows ISO download | `f_0085..f_0100` | "Download and Install Windows 11", live MB/sec + ETA, then "Weryfikowanie…" |
| 10 | Windows Setup runs | `f_0105..f_0140` | Windows 11 Setup boots inside Parallels' "Kreator instalacji" chrome; auto-progresses 0→100% |
| 11 | OOBE + Parallels glue | `f_0143..f_0190` | Black-screen OOBE, "Zaczekaj chwilę, trwa sprawdzanie dostępności aktualizacji", "Może to potrwać kilka minut" |
| 12 | Windows EULA inside guest | `f_0195..f_0250` | "Umowa licencyjna systemu Windows", scrollable, *Akceptuję* |
| 13 | Parallels account / license | `f_0210..f_0225` | "Zaloguj się na koncie Parallels" (Apple/Facebook/Google SSO) + "Parallels Desktop — wersja próbna" with 14-day trial |
| 14 | Welcome page | `f_0255..f_0267` | Edge inside guest opens `parallels.com/products/desktop/welcome-win/` — "Windows 11 Installed Successfully" |

Total wall-clock time observed: ~22 min, of which ~15 min is unattended
download + Windows Setup loops. The user sees roughly 14 distinct
screens and clicks ~12 times.

---

## 2. Phase-by-phase walkthrough

### 2.1 DMG splash — *"Instalacja oprogramowania Parallels Desktop"*

- **Frames:** `f_0001..f_0007`
- **Window chrome:** standard mac DMG window titled "Install Parallels
  Desktop". Background image: dark mountain road photograph.
- **Content:** Big "Parallels® Desktop for Mac" wordmark on the left, a
  3D iconic app-tile rendering on the right. The icon doubles as a
  click target — caption *"Instalacja oprogramowania Parallels
  Desktop"* / "Install Parallels Desktop software" appears beneath it.
- **Actions:** single click target — the icon. No "Continue" button
  exists; the icon **is** the CTA.
- **Next:** EULA modal.

### 2.2 EULA — *"Umowa licencyjna użytkownika końcowego (EULA)"*

- **Frames:** `f_0008..f_0009`
- **Modal child window** of the DMG, titled "Instalacja oprogramowania
  Parallels Desktop".
- **Content:** scrollable Polish EULA. No checkbox required.
- **Actions:** *Odrzuć* / "Decline" (secondary), *Akceptuj* / "Accept"
  (primary, blue).
- **Next:** telemetry opt-in.

### 2.3 Telemetry — *"Program Parallels Customer Experience"*

- **Frames:** `f_0010..f_0011`
- **Modal**, no separate window chrome.
- **Content:** ~6 lines of body text in Polish: "help us improve
  Parallels by automatically sending anonymous usage statistics", "data
  cannot be used to identify or contact you", "you can opt out at any
  time in Preferences", with a privacy-policy hyperlink (*"zasadach
  ochrony prywatności"*).
- **Actions:** *Wyłącz* / "Disable" (secondary), *Włącz* / "Enable"
  (primary, blue, focused — implicit default is **opt in**).
- **Next:** download + init.

### 2.4 Download / init — *"Pobieranie..."* and *"Inicjalizacja Parallels Desktop..."*

- **Frames:** `f_0012..f_0019`
- **Content:** modal with the Parallels app icon, big bold "Parallels
  Desktop" header, sub-line *"Uruchamiaj system Windows i jego
  aplikacje na Macu dzięki bezproblemowej integracji – bez ponownego
  uruchamiania komputera!"* / "Run Windows and its apps on Mac with
  seamless integration — without restarting the computer!"
- **Progress bar** with live caption *"188,7 MB z 193,2 MB - prawie
  gotowe..."* / "188.7 MB of 193.2 MB - almost done…". Total payload
  ~193 MB. After download completes, copy switches to *"Inicjalizacja
  Parallels Desktop..."* / "Initializing Parallels Desktop…" with an
  indeterminate bar.
- **Actions:** none — modal blocks until ready.
- **Next:** Touch ID prompt.

### 2.5 macOS auth gate — Touch ID / password

- **Frames:** `f_0014..f_0016`
- **Native macOS prompt:** "Parallels Desktop" wants to begin
  installation. *"Aby na to pozwolić, użyj Touch ID lub podaj hasło"* /
  "To allow this, use Touch ID or enter your password". Buttons
  *Anuluj* / "Cancel", *Użyj hasła…* / "Use Password…".
- **Note:** the password is *not asked again later* in this run —
  Parallels gets one privileged auth at install time and reuses it.

### 2.6 First app launch — *"Uprawnienia oprogramowania Parallels Desktop"*

- **Frames:** `f_0022..f_0035`
- **Window** is now the actual Parallels app, no longer the DMG.
- **Header:** *"Uprawnienia oprogramowania Parallels Desktop"* /
  "Parallels Desktop permissions". Body: "to enable all features,
  Parallels Desktop needs access to various directories. If you don't
  allow access, some features may not work or may not work correctly."
- **Body illustration:** stylized diagram of three folder rows with
  fake "Allow" buttons (`f_0025`).
- **Hyperlink at bottom:** *"Dlaczego oprogramowanie Parallels Desktop
  wymaga dostępu do tych folderów"* / "Why Parallels Desktop needs
  access to these folders".
- **Action button:** *Dalej* / "Continue" (primary, blue).
- **Behavior:** clicking *Dalej* triggers the **native macOS folder-
  permission dialogs sequentially** — Documents (`f_0028`), Downloads
  (`f_0030`), Desktop. Each native prompt has *Nie pozwalaj* / "Don't
  allow" and *Pozwól* / "Allow". After all three are granted, the
  in-app screen updates to show three green checkmarks for
  Desktop/Documents/Downloads (`f_0033`) and the bottom button changes
  to *Zakończ* / "Finish".
- **Next:** OS chooser.

### 2.7 OS chooser — *"Utwórz nowy"* / "Create new"

- **Frames:** `f_0040..f_0073`
- This is the heart of the wizard and deserves close attention. It is a
  **single screen, two-zone layout**:
  - Top zone: two large square tiles, *"Uzyskaj Windows 11 od firmy
    Microsoft"* / "Get Windows 11 from Microsoft" (Windows 11 logo with
    download arrow) and *"Zainstaluj system Windows, Linux lub macOS z
    pliku obrazu"* / "Install Windows, Linux or macOS from an image
    file" (generic disk-image icon).
  - Bottom zone, separator + heading *"Systemy darmowe"* / "Free
    systems": a horizontally-scrollable carousel of tiles. Visible at
    once: macOS, Ubuntu Linux, Fedora Linux, Debian GNU/Linux, Kali
    Linux. A `>` chevron at the right edge implies more.
  - Each carousel tile is `[icon] Pobierz <distro>` / "Download
    <distro>".
- **Footer buttons:** `?` help icon (left), *Otwórz…* / "Open…"
  (file-picker for ISOs, only shown after a tile is highlighted),
  *Wstecz* / "Back" (secondary, when applicable), *Pobierz* /
  "Download" or *Kontynuuj* / "Continue" (primary, contextual).
- **Behaviour:** hovering or selecting a tile pops a right-side detail
  pane with description, package size, and unpacked size — observed
  values:

  | Tile | Detail title | Size | Unpacked |
  |---|---|---|---|
  | Pobierz Ubuntu Linux (`f_0045..f_0048`) | *Ubuntu 24.04 ARM64*, *Wolny* / "Free" | 3.3 GB | 7.62 GB |
  | Pobierz Fedora Linux (`f_0055`) | *Fedora 40 ARM64*, *Wolny* | 3.58 GB | 5.91 GB |
  | Pobierz Debian GNU/Linux (`f_0060`) | *Debian GNU Linux 12.6*, *Wolny* | 1.9 GB | ~6.3 GB |
  | Pobierz Kali Linux (`f_0070`) | *Kali Linux 2024.2 ARM64*, *Wolny* | 4.78 GB | 15.65 GB |
  | Pobierz macOS (`f_0042..f_0044`) | *macOS 15.0.1 (24A348)*, "for non-commercial use", "Productivity and integration features…" | not shown | not shown |

- **Selection state:** the currently-selected tile gets a subtle blue
  fill (visible on the macOS Apple-logo tile in `f_0044` and the
  Debian tile in `f_0065`).
- **Note on the macOS tile:** Apple Silicon hosts get an extra
  "macOS-as-guest" path that x86 hosts presumably don't. This is
  surfaced in the same carousel as the Linux distros.

### 2.8 Custom-ISO mode — *"Wybierz ręcznie"*

- **Frames:** `f_0075`
- Triggered by selecting the *"Zainstaluj…z pliku obrazu"* tile.
- **Content:** *"Utwórz nowy"* header retained, big disk-image icon,
  spinner caption *"Wyszukiwanie obrazów instalacji na komputerze
  Mac..."* / "Searching for installation images on the Mac…", plus a
  hyperlink *"Gdzie mogę znaleźć obraz?"* / "Where can I find an
  image?" and a *Wybierz ręcznie* / "Choose manually" button.
- **Actions:** *Wstecz* / "Back" (active), *Kontynuuj* / "Continue"
  (disabled until an image is found).
- **Behavior:** Parallels auto-scans the user's Mac for ISOs/installers
  before falling back to a manual chooser — a very nice touch.

### 2.9 Windows-from-Microsoft splash — *"Pobierz i zainstaluj system Windows 11"*

- **Frames:** `f_0037`, `f_0080..f_0082`
- Triggered by clicking the Windows tile in the chooser.
- **Content:** large Win11 wallpaper render on the left; on the right,
  three short paragraphs:
  1. "You must install Windows 11 on your Mac to run Windows
     applications. If you'd like a different OS or a manual install,
     skip this step."
  2. "Windows 11 works great in Parallels Desktop, but there are some
     [*ograniczenia* / limitations] (link)."
  3. "You will have to activate this copy of Windows 11 after install."
- **Footer buttons:** `?` help, *Otwórz…* / "Open…" (alternative ISO),
  *Wstecz* / "Back", *Zainstaluj Windows* / "Install Windows" (primary,
  blue).
- **Note:** Parallels openly states "you'll need to activate later" —
  no pretence of bundled licensing.

### 2.10 Windows download progress

- **Frames:** `f_0085..f_0095`
- **Header:** "Download and Install Windows 11" (English, untranslated
  — small localization gap).
- **Body:** *"Instalacja rozpocznie się automatycznie. Tymczasem
  [zobacz](link), jakie możliwości oferuje Parallels Desktop for Mac"*
  / "Installation will start automatically. In the meantime, [see]
  what Parallels Desktop offers."
- **Progress bar** with live counter: observed values `71.8 MB / 3.9 GB
  (19 MB/sec) - 4 minutes left` → `1.35 / 3.9 GB - 2 min left` → `2.72
  / 3.9 GB - 1 min left`. Speed and ETA both refresh.
- **Actions:** *Anuluj* / "Cancel" (primary, blue), *Przerwij* /
  "Abort" (secondary). Double CTA — see §5 for critique.
- **After download:** progress bar switches to a striped indeterminate
  state with caption *"Weryfikowanie..."* / "Verifying…" (`f_0100`),
  buttons become *Anuluj* (now secondary) and *Wznów* / "Resume"
  (disabled).

### 2.11 Windows Setup runs inside Parallels — *"Kreator instalacji"*

- **Frames:** `f_0105..f_0140`
- **Window chrome change:** the entire Parallels window is now titled
  *"Kreator instalacji"* / "Installation Wizard" with a subtle spinner
  next to it and an inert *Kup* / "Buy" green button in the top-right
  (this Buy button persists from here through the rest of the wizard).
- **Content:** standard Microsoft Windows 11 Setup screens running
  inside the VM, full-screen on a black backdrop. Visible in order:
  - Win11 startup logo (`f_0105`)
  - Native Win11 Setup window *"Wyszukiwanie dysków"* / "Searching for
    disks", with Microsoft footer (`f_0115`)
  - Bright-blue *"Instalowanie systemu Windows 11 — Komputer zostanie
    uruchomiony ponownie kilka razy"* / "Installing Windows 11 — The
    computer will restart several times" with live percentage:
    `Ukończono 20%` (`f_0120`) → `51%` (`f_0125`) → `81%` (`f_0130`).
  - Black-screen reboot (`f_0135`)
  - Black "Trwa instalowanie 42% — Nie wyłączaj komputera" /
    "Installing 42% — Do not turn off the computer" (`f_0140`)
  - Brief flash of `cmd.exe` window (`f_0145`) — Parallels-injected
    post-install glue, e.g. driver/Tools install. Mildly alarming for
    end users.
- **Concurrent macOS prompts:** during this phase, native macOS
  permission dialogs interrupt — `f_0110` shows a "Parallels Desktop
  chce uzyskać dostępu do kamery" / "Parallels Desktop wants camera
  access" prompt overlaid while a `winpeshl.exe` window flashes
  underneath. **This is a UX wart** — see §5.
- **Persistent toast:** throughout this phase, an in-window toast at
  the bottom reads *"Instalowanie Windows 11. Proces ten zajmuje
  zazwyczaj 5–15 minut. Nie przerywaj go. Tymczasem [zobacz](link),
  jakie możliwości oferuje Parallels Desktop"* with a `×` close button.

### 2.12 OOBE + post-install glue

- **Frames:** `f_0150..f_0190`
- Long stretch of black/loading frames — many sampled frames are
  visually identical (just black or the dim Win11 logo).
- **Notable screens within:**
  - Dim Win11 logo on white-ish wash (`f_0175`) — Win11 OOBE prep.
  - Modern Win11 setup card (`f_0180`): green/blue/teal abstract
    geometry on the left, *"Zaczekaj chwilę, trwa sprawdzanie
    dostępności aktualizacji"* / "Please wait, checking for updates"
    on the right with a loading ring. Standard Win11 OOBE.
  - Deep-purple "Może to potrwać kilka minut. Nie wyłączaj komputera"
    (`f_0190`) / "This may take a few minutes. Do not turn off the
    computer."

### 2.13 Windows EULA presented again

- **Frames:** `f_0195..f_0250`
- Now inside the Parallels chrome (no Windows chrome) — *"Umowa
  licencyjna systemu Windows"* / "Windows License Agreement", subhead
  *"Zapoznaj się z umową licencyjną"* / "Review the license
  agreement". Long scrollable Polish Microsoft EULA (last-updated
  *kwiecień 2024*).
- **Single button:** *Akceptuję* / "I accept" (primary). No decline.

### 2.14 *"Instalacja ukończona"* / "Installation complete" overlay

- **Frames:** `f_0200`, `f_0220`
- Big animated green checkmark superimposed over the EULA / login
  card with caption *"Instalacja ukończona — Kliknij, aby
  kontynuować"* / "Installation complete — Click to continue".
- This is a **decorative confirmation** — clicking dismisses it and
  reveals the next screen.

### 2.15 Parallels account sign-in — *"Zaloguj się na koncie Parallels"*

- **Frames:** `f_0215..f_0225`
- **Layout:** two columns. Left: radio toggle *Jestem nowym
  użytkownikiem* / "I'm a new user" (default) vs *Mam hasło* / "I have
  a password", with fields E-mail / Nazwa użytkownika / Hasło /
  Potwierdź hasło. Right: *Inne opcje logowania* / "Other login
  options" with three SSO buttons — *Zaloguj się przez konto Apple* /
  "Sign in with Apple", *Zaloguj się używając Facebooka* / "Sign in
  with Facebook", *Zaloguj się z Google* / "Sign in with Google".
- **Primary CTA:** *Utwórz konto…* / "Create account…" (full-width
  blue button under the form).
- **Footer:** `?` help, *Business Edition* button (left).
- **Behaviour:** clicking the Google SSO option pops a native macOS
  modal *"Zaloguj się i zezwól oprogramowaniu Parallels na dostęp do
  danych konta Google w przeglądarce"* / "Sign in and allow Parallels
  to access Google account data in the browser" with *Anuluj* /
  "Cancel" (`f_0225`).
- **Mandatory account?** Yes — there is no "skip" option visible.

### 2.16 Trial banner — *"Parallels Desktop — wersja próbna"*

- **Frames:** `f_0205..f_0210`
- **Caption:** *"Okres próbny kończy się 10.11.2024. Liczba dni do
  wygaśnięcia licencji: 14"* / "Trial period ends 10.11.2024. Days
  until license expiration: 14".
- **Three actions** in a row at the bottom: *Kup* / "Buy", *Wprowadź
  klucz* / "Enter key", *Kontynuuj korzystanie z wersji próbnej* /
  "Continue using the trial".
- **Critique:** three competing CTAs, the trial-continue one is the
  longest text and visually equal-weight to the others.

### 2.17 Welcome to Windows web page

- **Frames:** `f_0255..f_0267`
- Edge browser inside the guest, address bar shows
  `parallels.com/products/desktop/welcome-win/`. H1 reads "Windows 11
  Installed Successfully", body: "Use it just like you would on a
  PC.* Next step: activate your copy of Windows 11."
- A *"Przetłumacz stronę z angielski?"* / "Translate page from
  English?" Edge widget pops up (`f_0255`) — Windows guest is in pl_PL
  too, so Edge offers translation. Visible cookie banner at the
  bottom.
- **Critique:** the welcome page is shown *inside the guest's Edge
  browser*, not on the macOS host. Awkward — the user just spent 22
  minutes in the host wizard, and the success confirmation moves the
  goalposts to the guest's browser.

---

## 3. OS installation paths offered

The chooser surface (§2.7) exposes **eight distinct install paths** in
two visual zones. Cataloguing them as if for a feature table:

| # | Path | Trigger | What Parallels asks for | Automation |
|---|---|---|---|---|
| 1 | **Windows 11 from Microsoft** | Top-left big tile | Nothing — fetches Microsoft's official Windows 11 ISO automatically | Fully automatic: download → ISO mount → Windows Setup → OOBE auto-pilot. User clicks once and the next interactive screen is the Parallels account login (§2.15). |
| 2 | **Custom ISO** | Top-right big tile | A path to an ISO/dmg file. Parallels first auto-scans the Mac for known images (`f_0075`); manual chooser as fallback. | Manual: user must walk through the OS's own installer once selected. |
| 3 | **Ubuntu Linux** | Carousel tile | Nothing | Fully automatic: ships a *prebuilt VM image* (3.3 GB pkg → 7.62 GB unpacked). Not an ISO — a turnkey image. |
| 4 | **Fedora Linux** | Carousel tile | Nothing | Same as Ubuntu — prebuilt image, 3.58 GB → 5.91 GB. |
| 5 | **Debian GNU/Linux** | Carousel tile | Nothing | Same model — 1.9 GB → ~6.3 GB. |
| 6 | **Kali Linux** | Carousel tile | Nothing | Same model — 4.78 GB → 15.65 GB. The carousel description specifically mentions security audits and pen-testing. |
| 7 | **macOS** (Apple Silicon hosts only) | Carousel tile | Nothing | Fetches macOS 15.0.1 (24A348) image. Note explicitly: "for non-commercial use". |
| 8 | **More distros (chevron)** | `>` arrow at right of carousel | n/a | Carousel scrolls to reveal additional OSes; only the five above were observed in this recording. |

**Key observations:**

1. The Linux and macOS paths are **prebuilt VM images, not ISOs +
   automated installers**. Parallels has done the install once,
   themselves, and ships the result. This eliminates entire classes of
   guest-installer failure (partitioning, locale, network configuration
   prompts) but means Parallels is effectively running a CDN of
   pre-configured VM images. CrossDesk should consider this for Linux
   guests at minimum.
2. The Windows path is the **only one that runs the OS's native
   installer** in this flow. Parallels has chosen not to ship a
   prebuilt Windows image — presumably because of licensing, not
   because they couldn't.
3. The chooser is **non-modal in spirit** — every option is a tile,
   the difference between "official Microsoft" and "free Linux" is
   marked by section heading, not by a tab or a wizard step. The user
   absorbs the full menu in one glance.

---

## 4. Configuration options matrix

Cataloguing every checkbox, radio, dropdown, file picker, button-pair,
and free-text field across the recording.

| # | Control | Where seen | Default | Semantic |
|---|---|---|---|---|
| 1 | EULA Accept/Decline (button pair) | EULA modal `f_0008` | none focused | Hard gate |
| 2 | Telemetry Enable/Disable (button pair) | `f_0010` | *Włącz* (Enable) is the focused/blue button — implicit opt-in | Anonymous usage stats |
| 3 | Touch ID / *Użyj hasła* fallback | `f_0015` | none | macOS native auth |
| 4 | Folder-access *Pozwól* / *Nie pozwalaj* (×3) | `f_0028..f_0030`, `f_0032` | none | Documents, Downloads, Desktop. All three required by wizard before *Zakończ* enables. |
| 5 | Windows tile vs Image tile vs Free-distro tile | `f_0040..f_0073` | nothing pre-selected | Install path |
| 6 | Free-distro carousel chevron `>` | `f_0040`, `f_0072` | n/a | Reveals more distros |
| 7 | *Otwórz…* (file picker for custom ISO) | `f_0048`, `f_0075` | hidden until "Image" tile chosen | Custom ISO path |
| 8 | *Wybierz ręcznie* (fallback file picker after auto-scan) | `f_0075` | n/a | Manual ISO selection |
| 9 | Windows splash *Inne opcje…* / *Zainstaluj Windows* | `f_0037` | *Zainstaluj Windows* primary | Choose Microsoft download or skip to image picker |
| 10 | Download progress *Anuluj* / *Przerwij* | `f_0085..f_0095` | *Anuluj* is primary blue (cancel = primary, abort = secondary — confusing) | Cancel vs pause |
| 11 | Verify-stage *Wznów* (Resume) | `f_0100` | disabled | Re-trigger verification |
| 12 | In-VM Microsoft Setup screens | `f_0115..f_0140` | n/a | Native Windows installer; Parallels does not interpose |
| 13 | Toast close `×` | `f_0105` | n/a | Dismisses "Installing 5–15 min" toast; persistent until clicked |
| 14 | Windows EULA *Akceptuję* | `f_0195` | none | Cannot decline |
| 15 | Parallels account *Jestem nowym użytkownikiem* / *Mam hasło* (radio) | `f_0215` | *Jestem nowym użytkownikiem* | New vs returning |
| 16 | E-mail / Nazwa użytkownika / Hasło / Potwierdź hasło (free-text) | `f_0215` | empty | Account fields |
| 17 | Apple / Facebook / Google SSO buttons | `f_0215` | none | Federated sign-in alternative |
| 18 | *Utwórz konto…* primary CTA | `f_0215` | enabled when fields valid | Create account |
| 19 | *Business Edition* footer button | `f_0215` | n/a | Switches to enterprise license flow |
| 20 | Trial: *Kup* / *Wprowadź klucz* / *Kontynuuj korzystanie z wersji próbnej* (3 buttons) | `f_0205` | none focused; equal weight | Buy now / enter key / use trial |
| 21 | Persistent green *Kup* / "Buy" in title bar | `f_0105..f_0210` | n/a | Always-on upsell affordance |
| 22 | `?` help icon (footer) | every wizard screen | n/a | Help, never observed clicked |
| 23 | *Wstecz* / *Kontynuuj* (footer pair) | most chooser screens | n/a | Standard wizard navigation |

**Notable absences in this flow:**

- No CPU-count slider, no RAM dropdown, no disk-size picker, no
  network-mode selector, no shared-folders toggle. Parallels has
  *deliberately hidden* every VM-tuning knob during first install. All
  of these presumably exist somewhere in Preferences but the wizard
  refuses to surface them. Compare CrossDesk's current `system-info`
  panel which exposes raw libvirt fields.
- No keyboard layout, locale, or timezone prompt — Parallels infers
  from macOS.
- No anti-virus / Defender opt-out.
- No "boot once and let me click through OOBE myself" escape hatch.
- No Windows-edition picker (Home / Pro / Enterprise) — Parallels
  picks for the user.

---

## 5. UX patterns to borrow vs avoid for CrossDesk

### 5.1 Patterns to borrow

1. **Prebuilt OS images for free distros (`f_0040..f_0070`).** Five
   Linux distros plus macOS, each as a zero-config download.
   CrossDesk's current docs assume Windows-only; consider shipping a
   prebuilt Ubuntu or Fedora image too, as a "demo guest" path that
   works without a Microsoft account. Even if our primary use case is
   Windows, the fallback option is a credibility signal.
2. **Single-screen install-path chooser, two zones** (`f_0040`). Big
   tiles for the headline option (Windows from Microsoft) plus a
   carousel for the "everything else" set. No tabs, no wizard
   branching at the entry point — every path visible at once. CrossDesk
   should use the same pattern even if the carousel only has 1–2
   entries at MVP.
3. **Auto-scan of the user's disk for ISOs** (`f_0075`). Parallels
   spins for ~2 seconds to find any DVD/ISO/.dmg the user may have
   already downloaded before falling back to a manual file picker.
   Tiny detail, big polish. CrossDesk should auto-scan `~/Downloads`,
   `~/Desktop`, and `~/Documents` for `.iso`.
4. **Live download counter with three values** (`f_0085..f_0095`):
   "1.35 / 3.9 GB (19 MB/sec) - 2 min left". MB count, throughput, ETA
   — all three. CrossDesk should match this format exactly.
5. **The toast "this takes 5–15 min, do not interrupt" with a
   dismiss `×`** (`f_0105`). Sets correct expectations during the long
   Windows-Setup phase. Same toast persistent across phase changes.
6. **Front-load all permissions before any productive work**
   (`f_0028..f_0033`). Documents, Downloads, Desktop access requested
   *all up front*, with a final confirmation screen showing 3 green
   checkmarks. CrossDesk should do the same with our libvirt /
   /dev/kvm / virtiofs permission surface — not lazily on first use.
7. **One macOS auth challenge, ever** (`f_0015`). The user types their
   password once, at install. They are not prompted again to start
   VMs, mount disks, or anything else.
8. **Windows EULA inside the wizard chrome** (`f_0195`), not as a
   modal popup, not as the Microsoft-Setup screen. Treats it as part
   of the on-ramp.
9. **Auto-fetched Windows ISO from Microsoft** (`f_0085`). The user
   does not have to know about `media.microsoft.com` or click through
   four Microsoft pages. CrossDesk's bootstrap pipeline should embed
   the same logic.
10. **No CPU/RAM/disk knobs in first-run UX**. Hard agreement —
    CrossDesk should not show users a libvirt domain XML editor at
    install time.

### 5.2 Patterns to avoid

1. **Five+ consent prompts before the first productive screen**
    (`f_0008` EULA → `f_0010` telemetry → `f_0015` Touch ID → `f_0028`
    Documents → `f_0030` Downloads → `f_0032` Desktop → `f_0040`
    chooser). That's 6 clicks of "Allow/Accept" before the user can
    *do* anything. Consolidate where possible — at minimum, fold
    Documents/Downloads/Desktop into one combined consent.
2. **Telemetry opt-out is a deliberate-friction button**
    (`f_0010`): *Wyłącz* is on the left as secondary, *Włącz* is
    pre-focused on the right as primary blue. Defaulting to opt-in is
    a dark-pattern; CrossDesk's GPL ethos should have this default
    *off*.
3. **Camera permission asked mid-Windows-install** (`f_0110`). The
    macOS native dialog "Parallels Desktop chce uzyskać dostępu do
    kamery" pops up while `winpeshl.exe` is doing a sysprep pass
    underneath. Should be batched with §2.6.
4. **The "Verifying…" striped progress with disabled *Wznów*** button
    (`f_0100`): suggests the user might need to resume verification,
    but the button is disabled. Confusing affordance — either show a
    clear "no action needed" message or hide the button.
5. **Cancel-as-primary-blue, Abort-as-secondary** during Windows
    download (`f_0085`). *Anuluj* (Cancel) is the blue button, *Przerwij*
    (Abort) is the white button — but during a download the *cancel*
    is the destructive option. Affordance inversion. CrossDesk should
    keep destructive actions secondary, never primary.
6. **The persistent green *"Kup"* (Buy) button in the title bar**
    (`f_0105..f_0210`). On every wizard screen for 15+ minutes. Visual
    nag during a flow the user already paid attention to. CrossDesk is
    GPL; this isn't a temptation, but the lesson — don't put upsell
    affordances in chrome — generalises.
7. **Three competing trial CTAs**, all visually equal-weight
    (`f_0205`): *Kup* / *Wprowadź klucz* / *Kontynuuj korzystanie z
    wersji próbnej*. The user just sat through 22 minutes; making them
    choose between buying, entering a key, or "continue trial" with no
    clear default is decision fatigue. CrossDesk should pick a single
    primary CTA per screen.
8. **Mandatory Parallels account** (`f_0215`). No "skip" affordance.
    Forces creation of an online account just to use the product — a
    classic enterprise SaaS-creep pattern. CrossDesk should never gate
    local virtualization on a network signup.
9. **Welcome page rendered inside the guest's Edge** (`f_0260`). The
    success confirmation lives at `parallels.com/products/desktop/
    welcome-win/`, viewed in the brand-new Win11 guest's Edge browser.
    Cute marketing tactic but the user has just spent 22 minutes on the
    host and their attention should resolve back to the host. CrossDesk
    should display "your guest is ready" *on the host*.
10. **English string left untranslated in pl_PL build** (`f_0085`):
    "Download and Install Windows 11" header in the otherwise-Polish
    UI. Small but visible — flag for our own i18n test suite.
11. **`cmd.exe` window flash mid-install** (`f_0145`). A black `cmd.exe`
    window appears for ~1 frame inside Windows during the post-install
    glue. Looks like malware. Suppress shell windows or use silent
    invocation flags.
12. **Long stretches of identical black/loading frames** (Windows
    install phase): from `f_0150` to `f_0175` the user stares at a
    near-black screen with at most a small Win11 logo. The toast from
    §2.11 helps but is not omnipresent. Add a low-frequency status
    line ("Step 3 of 5: configuring user account…") to give a sense of
    progress when the underlying installer is opaque.

### 5.3 Things Parallels does that are neutral but interesting

- **The macOS-as-guest carousel tile** (`f_0044`). Apple Silicon hosts
  get to install macOS-in-macOS as a first-class option. Probably
  irrelevant for CrossDesk on Linux, but it shows that Parallels treats
  "free OS" and "the host OS" as just more tiles in the same picker.
- **Trial banner shows exact expiry date and day-count** (`f_0205`):
  "10.11.2024. Liczba dni do wygaśnięcia licencji: 14". Both representations
  for different mental models. Borrow if we ever do paid tiers.
- **The big celebratory checkmark overlay** (`f_0200`, `f_0220`): comes
  in as a translucent overlay that requires a click. Decorative but
  effective at signalling phase boundaries.

---

## 6. Open questions / unobserved

The 267-frame extraction necessarily misses anything that happened
faster than ~3 seconds, anything driven by hover or focus, and anything
the recorder chose not to demonstrate. Specifically:

1. **Hover and focus states.** Tile hover styling, button focus rings,
   keyboard navigation order — none of it is visible from frames. We
   know tiles can be selected (blue fill in `f_0044`, `f_0065`) but
   whether keyboard-only users can reach them, and in what order, is
   unknown.
2. **Animations and transitions.** The big-checkmark overlay
   (`f_0200`) almost certainly animates in; we see only static frames.
   Whether the chooser carousel scrolls smoothly or paginates by tile
   is also unknown.
3. **The full content of the Linux carousel.** The chevron at
   `f_0040` and `f_0072` implies more tiles to the right beyond Kali.
   We saw five (Ubuntu, Fedora, Debian, Kali, macOS) but the recorder
   never scrolled past Kali. CentOS, openSUSE, Pop_OS, Arch, etc., may
   or may not be there.
4. **The "Inne opcje…" branch from the Windows splash (`f_0037`).**
   This presumably leads to a Windows-edition picker or an
   alternative-ISO flow, but the recorder did not click it.
5. **What happens after *Wstecz* / Back from each wizard screen.** We
   only saw forward progression.
6. **The actual Parallels Preferences pane** where the hidden
   CPU/RAM/disk/network knobs live. Never opened in this recording.
7. **Failure modes.** No frames show the wizard handling a network
   drop during ISO download, a disk-full error, an ISO checksum
   mismatch, or a Microsoft-API outage. CrossDesk's robustness story
   should not be benchmarked against a happy-path-only recording.
8. **Activation flow.** The post-install welcome page (`f_0260`)
   directs the user to "activate your copy of Windows 11" but the
   actual activation UI was not exercised.
9. **Resource usage during install.** The recording does not show
   Activity Monitor, so we cannot tell what CPU/RAM Parallels itself
   was using, only what it was telling the user.
10. **Exact wall-clock timing.** Frames are sampled at scene-change +
    15s periodic; absolute timestamps were not preserved in filenames.
    Phase durations in §1 are approximate.

---

## 7. Summary cross-reference for CrossDesk action items

| Parallels behavior | CrossDesk implication | Priority |
|---|---|---|
| Prebuilt Linux/macOS VM images | Add an "Ubuntu demo guest" path in our installer | P1 |
| Single-screen chooser w/ tiles + carousel | Match this layout in our Qt6/QML wizard | P0 |
| Auto-scan for existing ISOs | `~/Downloads`, `~/Desktop`, `~/Documents` glob for `*.iso` | P1 |
| Live download counter (MB/sec/ETA) | Match exactly in our progress UI | P0 |
| Front-load all permissions | Group libvirt/kvm/virtiofs prompts at install, not at run | P0 |
| One auth challenge ever | Don't re-prompt after install | P0 |
| Auto-fetch Windows ISO from MS | Already implied by our autounattend-driven flow | P0 |
| No CPU/RAM/disk pickers in first-run | Defer to Preferences | P0 |
| Don't bury cancel/abort | Destructive actions stay secondary | P0 |
| No mandatory online account | Local install must work fully offline | P0 |
| Welcome confirmation on host, not guest | First-launch screen on host UI | P1 |
| Group permission prompts | One consent screen, not three sequential | P1 |
| Suppress mid-install console windows | Silent invocation of all guest-side glue | P1 |
| Status line during opaque installer phases | "Step N of M: …" overlay | P2 |
| Telemetry default-off | GPL-friendly default, never opt-in by default | P0 |
