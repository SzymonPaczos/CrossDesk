# Ograniczony builder i niezależne dowody

Wymaga Python 3.9+, Git i Codex CLI z `exec --output-schema` oraz `--json`.
Obsługiwane są macOS i Linux (grupy procesów POSIX). Przed użyciem wypełnij
preambułę i [spec bramek](gate-spec.example.json): pełny przyjęty SHA,
własna gałąź, zakres plików oraz wymagane komendy jako argv, bez powłoki.
Spec przygotowuje właściciel/orchestrator przed dispatchem, nie builder.
Komendy specu mają takie uprawnienia jak host; wymagają tego samego
zaufania co polecenia CI. Spec nie jest sposobem wykonywania komend z issue.

```sh
CODEX_GATE_SPEC=<prywatny-runtime>/gate-spec.json \
CODEX_TIMEOUT_SECONDS=1800 \
bash <toolkit>/templates/codex-builder/codex-builder.sh \
  <worktree> <brief.md> <prywatny-runtime>/report.json --model <model>
```

Kolejność: czysty zaakceptowany baseline → ograniczony proces Codex →
walidacja rzeczywistego SHA, commitów i zakresu → niezależne wykonanie
bramek → ponowne sprawdzenie SHA i czystości. Raport modelu pozostaje
deklaracją. Dopiero `report.json.receipt.json` może zawierać
`VERIFIED_COMPLETE`, z kodami faktycznych procesów i ocenionym SHA.
Nie jest to PASS niezależnego Reviewera ani upoważnienie do merge/deploy.
Model może zwrócić `ready_for_checks` i `exit_code: null` dla końcowych
bramek hosta; nie musi uruchamiać całej suity tylko po to, żeby host od razu
ją powtórzył. Wskazane testy w trakcie implementacji nadal służą diagnozie.

`CODEX_GATE_SPEC` jest wymagany. Pusta lista bramek wymaga jawnego
`allow_empty_gates: true`; nie jest domyślnym obejściem wymaganych testów.
Pominięcia, błędny raport i brak commita nie prowadzą do ukończenia.
Przy zablokowanym zapisie `.git` builder podaje blocker; orchestrator może
wykonać już autoryzowany commit, bez wyłączania sandboxa.

Raport i prywatny katalog logów są poza working tree. CLI wysyła JSONL do
otwartego deskryptora hosta; nie zapisuje `-o` pod ścieżkę, którą worker
mógłby zamienić w symlink. Host zapisuje raport/receipt atomowo względem
otwartego katalogu. Nie commituj logów ani promptów do korpusu.

Zmienne: `CODEX_PREAMBLE`, `CODEX_EFFORT` (domyślnie medium),
`CODEX_TIMEOUT_SECONDS` (domyślnie 1800), `CODEX_PYTHON` (domyślnie python3).
`CODEX_SCRATCH` zachowuje wcześniejszy jawny dodatkowy katalog zapisu;
nie wskazuj nim sekretów ani obcego projektu. Dodatkowe argumenty CLI
ograniczono do modelu, koloru, ephemeral i strict-config; wrapper nie
przyjmuje nadpisania sandboxa, approval_policy ani schematu wyjścia.

Kody: kod błędnego procesu jest zachowany; 124 oznacza timeout, 130
przerwanie, 125 brak potwierdzonego cleanupu po pozornej zieleni procesu,
2 błędny kontrakt/środowisko, 3 blocker lub niesprawdzony wynik.
Raport i receipt rozstrzygają, którego etapu dotyczy błąd.

`watchdog.py` udostępnia `run_process(argv, *, cwd, timeout, stdin=None,
stdout=None, stderr=None, env=None, grace=1.0)`. Zwraca słownik z exit_code,
timed_out, cancelled i duration_seconds. Kończy całą własną grupę także,
gdy rodzic wyszedł, zostawiając potomka. Proces celowo opuszczający grupę
wymaga zewnętrznego sandboxa/kontenera; watchdog nie jest taką granicą.
Obsługa SIGTERM działa na głównym wątku, wątkowy caller odpowiada za
przekazanie anulowania. Nie wymusza liczby żądań modelu ani limitu USD.

Źródło opcji: [OpenAI, tryb nieinteraktywny](https://learn.chatgpt.com/docs/non-interactive-mode)
oraz pomoc lokalnego `codex exec --help`, sprawdzone 2026-11-05.
