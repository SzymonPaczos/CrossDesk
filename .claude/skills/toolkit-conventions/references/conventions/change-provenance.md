# Konwencja: ślad intencji zmiany

Cel: z historii wynika, po co powstała zmiana, z jakiego zadania i jak ją
sprawdzono. Zakres: przygotowanie commita, review, squash oraz konfiguracja
provenance. Nie wymaga tworzenia commita przy zadaniu odczytowym.

## 1. Intencja i zadanie

Mała zmiana ma jednozdaniowe `Intent`. Dla zadania złożonego zaakceptowana
specyfikacja i prompt startowy są w `.claude/task-briefs/<task-id>.md`,
a `Task-Ref` wskazuje brief. Intencja odzwierciedla ostatni uzgodniony zakres,
łącznie z późniejszymi korektami użytkownika.

## 2. Format commita

```text
feat(scope): krótki rezultat

Intent: <co i dlaczego wynika z zaakceptowanego zadania>
Task-Ref: <TASK-ID | issue/PR URL | direct-conversation YYYY-MM-DD>
Gates: <rzeczywiste komendy/checki i wynik, w tym brak wykonania>
```

Zgodnie z D-019 stopka `Co-Authored-By` współtworzącego agenta jest dozwolona
i niewymagana, a `AI-Contribution` nie jest wymagane. Projekt może wymagać
stopki wpisem we własnym rejestrze decyzji.

## 3. Dane wyłączone z zapisu

Provenance nie zawiera sekretów, danych osobowych, prywatnych ścieżek, poufnych treści,
niezaufanych payloadów, ukrytych instrukcji ani chain-of-thought.
Nie zapisuje surowych transcriptów lub dumpów kontekstu.
Nie zgaduje nazwy modelu, której narzędzie nie ujawnia. Poufne zadanie
może użyć bezpiecznego identyfikatora i minimalnego opisu.

## 4. Odpowiedzialność

Autor zadania utrzymuje zaakceptowaną intencję i brief; autor commita
przenosi pola do historii. Reviewer porównuje je z diffem i dowodami.
Rozbieżność blokuje merge. Squash zachowuje uzgodnione pola.

## 5. Egzekwowanie

Szablon: `templates/gitmessage.txt`, instalowany jako `commit.template`.
Bieżący etap z D-002 jest raportowy: hook zgłasza `WARN` dla braków pól,
a Conventional Commit subject pozostaje blokujący.

Przejście po okresie próbnym 1–2 tygodni na wymagane pola zależy od decyzji
właściciela. Merge/revert, `fixup!`/`squash!` i jawnie oznaczone tiny changes
zachowują zwolnienia. Hook nie zastępuje odpowiedniego required checka w CI.

## 6. Pochodzenie artefaktu

Pola commita opisują intencję. Build provenance wiąże artefakt z konkretnym
źródłem i procesem budowania; oba ślady mają osobne znaczenie.
Wymagania wydania: [`ci-cd.md`](ci-cd.md).

Egzekwuje: hook sprawdza format w trybie z punktu 5; review sprawdza zgodność intencji z zadaniem i diffem.
