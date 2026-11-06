# Konwencja: budżet kontekstu agenta

Stack-agnostic. Zakres: co trafia do kontekstu każdej sesji agenta i każdego
subagenta, gdzie umieścić regułę, żeby działała tam, gdzie jest potrzebna,
i jak mierzyć koszt kontekstu.

Zasada: agent dostaje to, czego model nie wie — zakazy i kontrakty tego
projektu — tylko dla bieżącego zadania i w chwili, gdy są potrzebne.
Rejestry i historia zostają kompletne na dysku; zmienia się to, co się
ładuje.

Zmierzone w jednym adoptującym projekcie, dla skali problemu: krok startowy
sesji nakazywał odczyt pięciu plików stanu o łącznej wielkości ok. 625 KB
(`wc -c`), handoff narósł do 69 sekcji (`grep -c '^## '`), a pliki ładowane
zawsze miały 107 080 B (`git cat-file -s <rev>:<plik>` dla każdego).
Po zmianach z tej konwencji pliki ładowane zawsze miały 15 164 B. To miara
plików, nie całego promptu ani tokenów.

## 1. Start sesji

1. Sesja czyta jedną sekcję `handoff.md` i `status.md`.
2. Backlog czyta przez spis treści i `grep -n '^### <ID>'`, nigdy w całości.
   Spis treści jest warunkiem tej reguły
   ([`project-state-layout.md`](project-state-layout.md) pkt 10).
3. Mapę architektury, manifest dead code i historię czyta tylko przy pracy,
   której dotyczą.
4. Handoff ma jedną sekcję, którą nadpisuje następny zapis, do 8 KB. Starsze
   sekcje przenosi się do archiwum poza kontekstem (lokalnie, jak sam
   handoff). Reguła „nadpisz przy następnym etapie" bez słowa „jedna sekcja"
   pozwoliła handoffowi rosnąć przez dopisywanie.

## 2. Pliki ładowane zawsze: do 15 KB

Wlicza się: `CLAUDE.md`, `AGENTS.md` (Codex ładuje go sam), pliki
importowane przez `@` z tych dwóch oraz `.claude/rules/*.md` bez `paths:` we
frontmatterze — Claude Code ładuje je bez importu. Hook dopisujący tekst do
każdego promptu też jest kontekstem stałym, powtarzanym przy każdym prompcie;
nie powtarza treści `CLAUDE.md`.

Pomiar:

```sh
set -o pipefail
zawsze() {
  for f in CLAUDE.md AGENTS.md; do [ -f "$f" ] && echo "$f"; done
  grep -hoE '(^|[[:space:]])@[A-Za-z0-9._/~-]+' CLAUDE.md AGENTS.md 2>/dev/null \
    | sed 's/^[[:space:]]*@//'
  for f in .claude/rules/*.md; do
    [ -f "$f" ] || continue
    awk 'BEGIN{r=1} NR==1{if($0!="---")exit; next} $0=="---"{exit}
         /^paths:/{r=0; exit} END{exit r}' "$f" || echo "$f"
  done
}
zawsze | sort -u | xargs wc -c
```

Gdzie trafia reguła:

| Reguła | Miejsce |
|---|---|
| zakaz lub kontrakt, który agent może złamać bez dotykania konkretnej ścieżki | plik ładowany zawsze, jedna linia |
| reguła działająca przy pracy na określonych ścieżkach | `.claude/rules/<dziedzina>.md` z `paths:` — ładuje się sam |
| reguła egzekwowana bramką | jedna linia z nazwą bramki |
| procedura zadania (CI, audyt, wydanie, review) | `.claude/conventions/`, wskazana w mapie `CLAUDE.md` |
| wiedza ogólna modelu | nigdzie |

Reguła dziedzinowa nie trafia do `.claude/conventions/`: tam agent musi
wiedzieć, że ma zajrzeć. Kryterium `paths:` brzmi „główne działanie reguły
dotyczy tych ścieżek". `paths:` obejmujące prawie całe repo oszczędza
niewiele, bo plik ładuje się niemal zawsze.

## 3. Rejestr decyzji: skrót i pełny rejestr

- `.claude/rules/decisions.md` — skrót ładowany zawsze: zakazy i kontrakty,
  które agent może złamać, jedna linia na decyzję z jej identyfikatorem lub
  datą. Wlicza się do budżetu z §2.
- `.claude/decisions-register.md` — pełne wpisy w dotychczasowym formacie,
  nieładowane; wpis odczytuje się przez `grep -n '^### <ID lub data>'`.
- Skróty dziedzinowe mogą żyć w `.claude/rules/decisions-<dziedzina>.md`
  z `paths:`.

Format wpisu i zasada „decyzji się nie usuwa, zmienia się status" obowiązują
w pełnym rejestrze. Przeniesienie wpisu ze skrótu do rejestru nie jest
usunięciem. Migrację weryfikuje porównanie nagłówków przed i po
(`grep -E '^#{2,3} ' <plik> | sort` na obu wersjach, wynik identyczny) oraz
recenzja jedną soczewką: czy któraś reguła przestała się ładować tam, gdzie
działa.

## 4. `AGENTS.md` bez łańcucha lektur

`AGENTS.md`, który każe najpierw przeczytać `CLAUDE.md`, reguły i decyzje,
wciąga cały kontekst stały i pliki stanu do każdej sesji Codexa — także
buildera, który ma kompletny brief. Dlatego:

- kanoniczne instrukcje to `CLAUDE.md` i `.claude/rules/`; `AGENTS.md`,
  `.cursorrules` i `GEMINI.md` są wskaźnikami, nie drugim zbiorem reguł;
- `AGENTS.md` ma do 1 KB: builder z briefem pracuje według briefu; twarde
  zakazy są wypisane wprost; agent bez briefu zaczyna od `CLAUDE.md`;
- brief i preambuła niosą kontrakty, które zadanie może złamać (sekrety,
  migracje, ograniczenia UI, sieć). Builder spoza Claude Code nie dostaje
  `.claude/rules/` automatycznie, a zachowane nagłówki rejestru tego nie
  zastępują.

## 5. Builder nieinteraktywny

Szablony: [`templates/codex-builder/codex-builder.sh`](../templates/codex-builder/codex-builder.sh)
i [`templates/codex-builder/preamble.md`](../templates/codex-builder/preamble.md).
Kontrakt trybu oszczędnego:

- rozumowanie `medium` domyślnie, wyższe tylko jawną flagą;
- wyjście narzędzi ograniczone do 2000 tokenów; odczyt pliku do ok. 150 linii,
  celowane odczyty zależności (importy, wywołania, kontrakty) są dozwolone;
- brief do ok. 2 KB, ze ścieżkami `plik:linia`;
- poprawki po recenzji długiej sesji idą świeżą sesją z listą `plik:linia`;
  wznowienie wysyła przy każdym żądaniu całą dotychczasową historię. Krótką
  sesję wolno wznowić — świeży start też płaci za orientację;
- po ok. 60 żądaniach bez końca zadania builder przerywa i raportuje stan.
  Zdanie w preambule nie jest egzekwowanym limitem; twardy limit daje
  runtime ([`multi-agent-delivery.md`](multi-agent-delivery.md) §6);
- pełny szybki lane testów raz przed raportem, nie „testy powiązane":
  zapadki czytające pliki przez system plików do powiązanych nie trafiają;
- każdy potok z runnerem testów poprzedza `set -o pipefail`, a raport podaje
  kod wyjścia — `tail` i `grep` nie mogą ukryć czerwieni.

Zmierzone w tym samym projekcie (mediana wejścia na żądanie z unikalnych
zdarzeń `token_count` dziennika sesji Codexa, komenda w kontroli głębokiej
`weekly-audit` pkt 7): dwie sesje w trybie wcześniejszym 132 078 i 168 212
tokenów, dwie w trybie oszczędnym 44 488 i 26 870. Zadania w trybie
oszczędnym były mniejsze, więc różnicy nie wolno w całości przypisać trybowi.

## 6. Pozycja backlogu

- Nowa lub zmieniana pozycja ma do 1 500 B, a notka stanu do 4 linii.
- Narracja wykonania (przebiegi, próby, kto co sprawdził) idzie do
  `history/`, nie do pozycji.
- Limit dotyczy pozycji, nie pliku: po §1 nikt nie czyta backlogu w całości.
  Identyfikatory i kotwice zostają, bo opierają się na nich bramki.

## 7. Subagenci i sesja główna

- Prompt subagenta podaje listę plików i zakazuje czytania plików stanu
  (backlog, handoff, historia), chyba że zadanie ich dotyczy.
- Role czytające (Scout, Coordinator) mogą działać na mniejszym modelu;
  dobór modelu per rola: [`multi-agent-delivery.md`](multi-agent-delivery.md) §6.4.
- Duże wyjścia sesja główna czyta przez `tail`/`head`, a diff do recenzji
  przekazuje plikiem.

## 8. Pliki użytkownika poza repo

Styl wyjścia, poziom rozumowania sesji i pluginy synchronizowane z konta też
trafiają do każdej sesji, ale żyją poza repozytorium. Toolkit ich nie
zarządza; ich koszt mierzy `/context` w świeżej sesji, a zmianę decyduje
właściciel.

## Egzekwowanie

Pomiar: skill `weekly-audit`, kontrola głęboka pkt 7 — budżet bajtów, koszt
sesji, użycie MCP i skilli, sensowność reguł.

Egzekwuje: audyt tygodniowy i review. Bramka szablonowa budżetu bajtów jest
zadaniem do zrobienia.
