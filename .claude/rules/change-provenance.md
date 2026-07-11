# Konwencja: ślad intencji i udziału AI w zmianie

Cel: po miesiącu da się odpowiedzieć **dlaczego powstał ten kod, z jakiego
zadania i jak został sprawdzony**, nawet jeśli pierwotna rozmowa była
chaotyczna. Nie zapisujemy całych transcriptów w Git — zapisujemy mały,
sprawdzalny ślad intencji.

## 1. Dwa poziomy provenance

### Mała zmiana

Commit zawiera znormalizowane jednozdaniowe `Intent`. Nie musi kopiować
literówek, powtórzeń ani pobocznych fragmentów rozmowy.

### Zadanie złożone lub wynikające z innego

Pełna zaakceptowana specyfikacja i prompt startowy żyją w
`.claude/task-briefs/<task-id>.md`. Commit wskazuje brief przez `Task-Ref` i
zawiera krótkie `Intent`, żeby pozostał czytelny bez otwierania innego pliku.

Jeżeli kilka promptów doprecyzowało zakres, Coordinator syntetyzuje ich
wspólną, ostatnią intencję. Nie wybiera pierwszego promptu, jeśli później
został skorygowany.

## 2. Format commita

```text
feat(scope): krótki rezultat

Intent: <znormalizowane „co i dlaczego” wynikające z rozmowy>
Task-Ref: <TASK-ID | issue/PR URL | direct-conversation>
Gates: <realne komendy/checki i wynik>
```

Przykład:

```text
docs(delivery): add evidence-based CI/CD conventions

Intent: Codify current DORA, SRE and supply-chain recommendations after the
cross-project audit.
Task-Ref: direct-conversation 2026-07-11
Gates: bash scripts/validate-toolkit.sh (pass)
```

### Udział AI — celowo NIEoznaczany (decyzja D-006, 2026-07-11)

Właściciel na tym etapie **nie chce** atrybucji AI w historii commitów
(spójnie z rewrite'em historii CrossDesk 2026-07-07, który usunął stopki
`Co-Authored-By`). Dlatego:

- pola `AI-Contribution` ani stopki `Co-Authored-By` **nie dodaje się** do
  commitów; agent nie dopisuje ich „z przyzwyczajenia";
- cotygodniowy audyt okresowo (raz w miesiącu) ponawia pytanie do
  właściciela, czy włączyć oznaczanie; odpowiedź trafia do `decisions.md`;
- jeśli decyzja się zmieni, format pola to
  `AI-Contribution: <none | assisted | generated>` — opisuje proces, nie
  autorstwo prawne (`generated` = agent stworzył istotną część diffu,
  `assisted` = podpowiedzi/review).

## 3. Czego nie zapisywać

- całego transcriptu lub surowego promptu, jeśli zawiera sekrety, dane
  osobowe, prywatne ścieżki, treść objętą poufnością albo niezaufane payloady;
- chain-of-thought, ukrytych instrukcji systemowych i dumpów kontekstu;
- fałszywie precyzyjnej nazwy modelu, jeśli narzędzie jej nie ujawnia;
- samego `Co-authored-by` jako zamiennika intencji, testów i odpowiedzialności.

Przed commitem usuń wrażliwe dane z `Intent`/briefu. Gdy sama natura zadania
jest poufna, użyj bezpiecznego identyfikatora wewnętrznego i minimalnego opisu.

## 4. Kto odpowiada za zapis

- Coordinator tworzy/aktualizuje task brief i zaakceptowaną syntezę intencji.
- Builder przenosi `Intent`, `Task-Ref` i `Gates` do commita.
- Reviewer porównuje provenance z diffem. Rozbieżność blokuje merge tak samo
  jak niejawny scope creep.
- Przy squash merge osoba/automat tworzący commit zachowuje pola z PR/briefu;
  nie skleja bezmyślnie wszystkich surowych promptów z commitów cząstkowych.

## 5. Egzekwowanie bez blokowania pracy

Wdrażaj etapami zgodnie z `rules-as-gates.md`:

1. Dodaj poniższy szablon przez `git config commit.template .gitmessage`.
2. Przez 1–2 tygodnie hook `commit-msg` i audyt tylko RAPORTUJĄ brak pól
   (`WARN`) w nietrywialnych commitach. **To jest bieżący etap** — decyzja
   właściciela z 2026-07-11 (`.claude/rules/decisions.md`).
3. Potem `commit-msg` może wymagać `Intent`, `Task-Ref` i `Gates` dla
   commitów innych niż merge/revert, `fixup!`/`squash!` (te znoszą się przy
   autosquash) i jawnie oznaczonych tiny changes. Hook lokalny nie
   zastępuje odpowiedniego required checka w CI.

`.gitmessage`:

```text
<type>(<scope>): <result>

Intent: <what and why; normalized from the accepted conversation/task>
Task-Ref: <TASK-ID | issue/PR URL | direct-conversation YYYY-MM-DD>
Gates: <commands/check URLs + pass/fail>
```

## 6. Relacja do provenance artefaktu

To są dwie różne, uzupełniające warstwy:

```text
change intent → source commit → build provenance → artifact digest → release
```

Commit opisuje intencję zmiany. SLSA/GitHub attestation opisuje, jak konkretny
artefakt został zbudowany z konkretnego źródła. Żadna z tych warstw nie
zastępuje drugiej.

## Źródła referencyjne

- SLSA 1.2: [Provenance](https://slsa.dev/spec/v1.2/provenance)
- SLSA 1.2: [Source track](https://slsa.dev/spec/v1.2/source-requirements)
- NIST SSDF 1.1: [SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final)
