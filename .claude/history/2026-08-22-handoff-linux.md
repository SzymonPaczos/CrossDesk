# Handoff — dokończenie audytu 2026-08-22 na boxie Linux

**Ten plik jest trackowany świadomie.** Poprzedni `handoff.md` był
nietrackowanym scratchem sesji, wypadł z drzewa (`709363b`) i zostawił martwe
cytaty §2.7/§2.8 w `status.md` i `backlog.md` — precedens do punktu 14d
(integralność referencyjna). Treść odzyskiwano potem z historii. Drugi raz nie.

## Stan w chwili zapisu

| Repo | Gałąź | SHA | Origin |
|---|---|---|---|
| CrossDesk | `chore/audit-toolkit-2026-08-20` | `5759e0f` (4 commity) | ✅ wypchnięte, **niezmergowane** |
| claude-toolkit | `main` | `983c137` (2 commity) | ✅ wypchnięte |

Toolkit `2026.08.21`, `check` zielony, jedno odstępstwo w `toolkit.local`.
Audyt: [`audit-log.md`](../audit-log.md) „## Audyt 2026-08-22”, znaleziska
w [`backlog.md`](../backlog.md).

## Dlaczego to wraca na Linuksa

Audyt 2026-08-22 przejechał na MacBooku. Trzy klasy pomiarów są tam
**niewykonalne albo zniekształcone**, a liczby z takiego przebiegu wyglądają
dokładnie jak liczby z dobrego. Poniżej lista do powtórzenia — z komendą i z
tym, co dany wynik znaczy.

### Warunek wstępny — Krok 00 na boxie jest DEGRADED

`~/DevProjects/claude-toolkit` **nie istnieje na boxie** (backlog P2, audyt
2026-07-22), więc `toolkit-sync.sh check` nie ma z czym porównywać, a
`test-gates.sh` (mieszka w toolkicie) jest nieosiągalny. Najpierw:

```sh
git clone https://github.com/SzymonPaczos/claude-toolkit.git ~/Projects/dev/claude-toolkit
bash ~/Projects/dev/claude-toolkit/scripts/toolkit-sync.sh check .
```

Bez tego audyt na boxie ponownie zaraportuje `DEGRADED` w Kroku 00, a bramka
sekretów pozostanie **niemierzalna**.

### 1. Warstwa statyczna mierzona poza venvem

Nagłówek raportu mówi `PYTHON_ENV: brak` — `host/.venv` nie istnieje na Macu,
więc `mypy` liczył typy bez zainstalowanych zależności projektu i zgłosił brak
importu `pycdlib` (**środowisko, nie regresja typów** — dlatego `audit.sh`
rozdziela te dwie liczby od 2026-08-21).

```sh
cd host && python -m venv .venv && . .venv/bin/activate && pip install -e .
cd .. && bash .claude/audit.sh          # dopisze sekcję do audit-log.md
```

Oczekiwane: `mypy --strict` nadal **0 błędów**, a braki importu spadają do **0**.
Cokolwiek innego = realne ustalenie, nie luka środowiska.

### 2. pytest nigdy nie przejechał do zielonego na Macu

Zebranych **1067**, ale suita wiesza się ~6% przebiegów na macOS (wyciekły
wątek `_poll_wrapper`, backlog P2). Na boxie była zielona w 44 s (audyt
2026-07-06). Bez świeżego baseline'u z boxa **nie da się ocenić żadnej z
napraw P0** — `test-evidence.md` mówi wprost: oceniaj po różnicy zbioru nazw
`FAILED`, nigdy po liczbie.

```sh
cd host && . .venv/bin/activate && pytest -q 2>&1 | tail -20
```

Zapisz listę `FAILED` jako baseline gałęzi bazowej **przed** dotknięciem P0.

### 3. Bramka `pre-push` jest niemierzalna, a wynik z Maca skażony

`test-gates.sh .githooks/pre-push` dał `4 zdanych, 2 niezdanych` — i tego
**nie wolno czytać jako 4/6**. Fixture nie ma katalogu `guest/`, więc
`pre-push:323` przewraca się na samym `cd` i melduje „found vulnerabilities”;
testy 2 i 3 padają z tego powodu, a test 1 „przechodzi” z **tego samego**
powodu, nie za wykrycie sekretu.

Kolejność jest wymuszona: najpierw **P1 1a** (rozdzielić `BLOCKED` od
findingu w warstwie 5), dopiero potem **P0 1** (czytanie refów ze stdin +
`git worktree`) ma czym się udowodnić.

```sh
bash ~/Projects/dev/claude-toolkit/templates/test-gates.sh .githooks/pre-push
```

Cel: **6/6 z niesprzecznych powodów**. Do tego czasu raport nie ma prawa
twierdzić, że skanowanie sekretów jest egzekwowane.

### 4. Zestawy narzędzi obu maszyn są rozłączne

| Narzędzie | MacBook | Box Linux |
|---|---|---|
| `zizmor` | **n/a** | jest (`~/.local/share/zizmor-venv`, 1.27.0) |
| `buf`, `qmllint`, `gitleaks` | są (0 findings) | **n/a** (audyt 2026-07-22) |
| libvirt / KVM / FreeRDP / Windows | **n/a** | jest |
| Qt6 (GUI się buduje) | jest | jest |

Żadna z maszyn nie mierzy kompletu. Audyt z boxa domknie kolumnę `zizmor`
(jedyne miejsce, gdzie da się sprawdzić workflowy) — ale **straci** trzy
warstwy, które na Macu wyszły zielone. Obie połówki trzeba zestawić, zanim
padnie zdanie „bramki są kompletne”.

### 5. `cargo-deny guest` = 25 wobec baseline'u 24

Backlog notuje **24** po bumpie otel (P1). Pomiar z Maca: **25**. Ten sam
`Cargo.lock`, więc albo to artefakt wersji narzędzia, albo realny wzrost — a
wzrost względem poprzedniego audytu to P2 z zapadką. Potwierdzić na boxie.

### 6. `DOCS_SOURCE` pusty → jedna klasa ustaleń nierozstrzygnięta

Bez podłączonego źródła dokumentacji audyt **nie ma prawa** podać daty EOL
Pythona jako faktu. Dlatego rozjazd `requires-python = ">=3.9"` wobec
**wyłącznie 3.12** w matrycy CI wisi w Inboxie jako P2 zamiast zostać
rozstrzygnięty. Jeśli 3.9 jest realnie wspierany i jest po EOL — punkt 15
mówi **P0**, nie P2. Do domknięcia przy pierwszym audycie ze źródłem.

### 7. Hooki nie były aktywne w klonie na Macu

`core.hooksPath` było **nieustawione** — czyli commity i pushe tej sesji
przeszły z pominięciem `pre-commit`, `commit-msg` i `pre-push`. Włączone
2026-08-22 (`git config core.hooksPath .githooks` + `commit.template`).
Ustawienie żyje w `.git/config`, jest per-klon i nietrackowane, więc
**sprawdź je na boxie tą samą komendą**, zanim uznasz tamtejsze bramki za
działające:

```sh
git config core.hooksPath      # oczekiwane: .githooks
```

To jest ta sama klasa, o którą chodzi w P0 wyżej: bramka niezainstalowana nie
jest bramką, a jej brak wygląda z zewnątrz jak zielony przebieg.

## Czego Linux NIE jest potrzebny

Reprodukcje dwóch P0 zrobiono na Macu i **są ważne** — to czysta logika
Pythona:

- **JIT-lite**: `$HOME/notatki.txt` → udostępniony **cały `$HOME`**;
  `$HOME` jako argument → **rodzic `$HOME`**, poza allowed root; oba przy
  `shared_folder_enabled = False`.
- **Ostrzeżenie `home`**: realny output to
  `{"event":"shared_folder_home_scope","warning":"<redacted>","redaction_drop_count":1}`.

Naprawy dla obu i ich testy regresji da się napisać i uruchomić lokalnie.
Live-verify potrzebuje boxa dopiero dla `steady-state.xml` (libvirt).

## Kolejność pracy po stronie boxa

1. Sklonuj toolkit → `toolkit-sync.sh check .` zielony (Krok 00).
2. `host/.venv` + `bash .claude/audit.sh` → porównaj z sekcją 2026-08-22.
3. `pytest` → zapisz baseline `FAILED` **przed** naprawami.
4. P1 1a → P0 1 (`pre-push`) → `test-gates.sh` **6/6**.
5. P0 JIT-lite → denylist `~/.config/crossdesk` + `~/.local/state/crossdesk`
   → P0 `steady-state.xml`. Kolejność i gotowy mechanizm: `backlog.md`
   „Kolejność naprawy tych trzech”.
6. Dopiero potem Faza C `loop-spec.md` (#3 FS Stage B, #5, #11, #12).

## Zablokowane decyzją właściciela

- **Kanał ostrzeżenia o scope `home`** — pole w `LaunchResponse` (edycja
  `proto/**` = boundary) czy stderr daemona? Bez tego P0 nr 4 nie rusza.
- **Tag `v0.1.0`** — odblokowuje kryterium #12 (PKGBUILD ciągnie tarball
  z nieistniejącego taga) oraz pin `sha256sums` (backlog C-1).
- **Dwie konwencje toolkitu** (`naming-conventions`, `module-paths`) —
  przyjąć czy jawnie odrzucić.
- **Merge gałęzi `chore/audit-toolkit-2026-08-20`** do `main`.
