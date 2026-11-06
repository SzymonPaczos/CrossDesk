# Konwencja: backlog jako kontrakt maszynowy

Stack-agnostic. Zakres: **jaki kształt ma pozycja w `.claude/backlog.md`, żeby
dało się ją przeczytać maszynowo, uporządkować i udowodnić jej domknięcie.**

Rozdział ról:

- [`project-state-layout.md`](project-state-layout.md) — **gdzie** leżą pliki
  stanu i który plik czemu służy. Ta konwencja niczego tam nie zmienia poza
  jednym: doprecyzowuje **wnętrze** `backlog.md`.
- [`issue-reporting.md`](issue-reporting.md) — zgłoszenie defektu na zewnątrz,
  dla cudzego repozytorium. Backlog jest wewnętrzny, ale warunek zamknięcia
  bierzemy stamtąd, zamiast wymyślać drugi.
- [`change-provenance.md`](change-provenance.md) — trailer `Task-Ref:`
  w commicie. To on spina zmianę z pozycją; bez niego domknięcia nie da się
  udowodnić.

## 1. Problem

Backlog był dotąd opisany wyłącznie od strony przeznaczenia: jeden plik, sekcje
priorytetów, pozycja znika gdy zrobiona. Nie miał **kształtu wpisu**. Skutek
zmierzony na trzech projektach jednej floty, zasilanych tym samym audytem
w odstępie dni: trzy niekompatybilne formaty — lista z polami w prozie, tabela
o siedmiu kolumnach, sekcje narracyjne.

Konsekwencje są konkretne, nie estetyczne:

- **nic nie czyta backlogu.** Wszystkie skille do niego piszą; żaden go nie
  bierze na wejście, bo nie wiadomo, co jest polem, a co zdaniem;
- **pozycja nie ma tożsamości.** Bez identyfikatora nie da się powiedzieć
  „ten commit zamyka tę pozycję", więc domknięcie jest deklaracją, nie faktem;
- **odłożenie jest nieodróżnialne od zapomnienia.** Pozycja świadomie odrzucona
  wygląda tak samo jak pozycja przeoczona, więc następny audyt zgłasza ją
  ponownie jako nową.

## 2. Kształt pozycji

Jedna pozycja to nagłówek trzeciego poziomu, blok pól `KLUCZ: wartość`, potem
dowolna proza.

```markdown
### AUD-2026-08-21-22 — dane czynności tylko na dysku

WPLYW: critical
STATUS: otwarte
ZRODLO: audyt 2026-08-21
DOWOD: git ls-files web/src/data/czynnosci/ → 0 przy 2 plikach na dysku
BRAMKA_ZAMYKAJACA: git clone --depth 1 . /tmp/k && cd /tmp/k && npm ci && npm test
PRZEGLAD: —
BRIEF: —

Wpis `data/` w `.gitignore:10` nie ma kotwicy, więc łapie też
`web/src/data/czynnosci/`. Pliki importuje `czynnosci.ts`, czysty klon się
nie zbuduje.
```

Klucze są **bez znaków diakrytycznych i bez spacji**. Powód jest praktyczny:
mają się dać wyciągnąć jednym wzorcem, tak samo jak `AUDITED_REVISION:`
i `NOWE_CZERWONE:` w raportach audytu. Korpus używa tego kształtu wszędzie tam,
gdzie coś ma czytać maszyna — backlog nie jest wyjątkiem.

| Klucz | Wartość | Obowiązkowy |
|---|---|---|
| `WPLYW` | `critical` / `high` / `medium` / `low` / `—` (w `Inbox` może być pusty) | tak |
| `STATUS` | `otwarte` / `w trakcie` / `zaparkowane` | tak |
| `ZRODLO` | `audyt <data>` / `rozmowa` / `zgloszenie <ref>` / `review <sha>` | tak |
| `DOWOD` | dlaczego to jest problem — komenda, ścieżka z linią, cytat | tak |
| `BRAMKA_ZAMYKAJACA` | **komenda**, albo `odstepstwo: <powód>` | tak |
| `PRZEGLAD` | data następnego spojrzenia albo `—` | tak (patrz §4) |
| `BRIEF` | `task-briefs/<id>.md` albo `—` | tak |

Tytuł pozycji jest **zdaniem o tym, co się dzieje**, nie kategorią. „Dane
czynności tylko na dysku" mówi czytelnikowi wszystko; „A-022, critical, dane" nie mówi
nic (`rules-as-gates.md` pkt 9). Identyfikator służy do wskazywania pozycji
w rozmowie i w `Task-Ref:`, nie do jej opisywania.

Klucz nieobecny jest **błędem, nie wartością domyślną**. Pozycja bez
`BRAMKA_ZAMYKAJACA` to pozycja, której nikt nie umie zamknąć, i lepiej, żeby
było to widać od razu.

Objętość: nowa lub zmieniana pozycja ma do 1 500 B razem z prozą, a notka
stanu pod polami do 4 linii. Przebieg wykonania — próby, przebiegi, kto co
sprawdził — idzie do `history/`, dłuższa analiza do briefu. Sesja czyta
backlog przez spis treści i `grep -n '^### <ID>'`, więc pozycja ma się dać
zrozumieć bez reszty pliku ([`context-budget.md`](context-budget.md) §1 i §6).

## 3. Identyfikator

Format: `<ZRODLO>-<RRRR-MM-DD>-<nn>`, na przykład `AUD-2026-08-21-22`. Data to
dzień powstania pozycji, nie dzień naprawy. Numer jest kolejny w obrębie dnia.

ID trafia do commita jako `Task-Ref:` — i to jest cały mechanizm dowodu.
`git log --grep='Task-Ref: AUD-2026-08-21-22'` odpowiada na pytanie „co
faktycznie zamknęło tę pozycję" bez zaufania do czyjejkolwiek deklaracji.

ID **nigdy nie jest ponownie użyte**, nawet gdy pozycja została odrzucona.
Numer jest tani, a odzyskany identyfikator sprawia, że historia kłamie.

## 4. Bramka zamykająca i przegląd

`BRAMKA_ZAMYKAJACA` jest **komendą do uruchomienia**, nie opisem zamiaru. Ma
być czerwona teraz i zielona po naprawie. To ta sama procedura, którą
[`test-evidence.md`](test-evidence.md) stosuje do testów: bramka, której nie
widziano czerwonej, nie dowodzi niczego.

Część pozycji nie ma naturalnej bramki — „dokumentacja opisuje stan sprzed
migracji", „repozytorium nie ma zdalnego". Wtedy wartością jest
`odstepstwo: <powód>` i **`PRZEGLAD` staje się obowiązkowa**. To przeniesienie
reguły z [`quality-gates-and-dod.md`](quality-gates-and-dod.md): wyjątek musi
wygasać automatycznie, a bramka odrzuca go po terminie.

`PRZEGLAD` jest obowiązkowa dla `STATUS: zaparkowane` i dla każdego odstępstwa.
Dla pozycji otwartej z działającą bramką wartością jest `—`.

## 5. Sekcje pliku

```
## Do wykonania (kolejność = decyzja właściciela)
## Inbox
## Poza kolejką (świadomie, z datą przeglądu)
## Czeka na decyzję właściciela
## Zablokowane (infra / zależności)
```

`## Do wykonania` zawiera pozycje w kolejności wykonania. Kolejność jest
planem: pozycja żyje w jednym miejscu, a jej miejsce na liście mówi, kiedy po
nią sięgamy. Osobny plik planu byłby drugim źródłem prawdy, które starzeje się
niezależnie. Nie ma osobnych sekcji według wpływu; wpływ jest polem pozycji,
nie koszem (decyzja z wersji 2026.09.07).

`## Poza kolejką` trzyma pozycje **świadomie odłożone**, każda z powodem
i datą. Różnica między „odłożone" a „przeoczone" jest tu widoczna, więc audyt
nie zgłasza ich ponownie jako nowych.

Wpływ mówi, jak bardzo boli. Kolejka mówi, co robimy najpierw. To dwie różne
rzeczy i mieszanie ich jest powodem, dla którego backlogi porządkowane
wyłącznie dotkliwością nigdy się nie kurczą: dwie pozycje `low` po dziesięć
minut potrafią być właściwszym początkiem niż jedna `high` na trzy dni.

## 6. Domknięcie

Pozycję zamykają **trzy rzeczy naraz**, nie jedna:

1. commit z `Task-Ref: <ID>`;
2. `BRAMKA_ZAMYKAJACA` uruchomiona i zielona, z dowodem, że przed zmianą była
   czerwona;
3. wpis w `history/completed-work.md`: identyfikator, data, komenda bramki, SHA.

Dopiero wtedy pozycja **znika z backlogu** — zgodnie z regułą „done ≠ open"
z [`project-state-layout.md`](project-state-layout.md). Dlatego `STATUS` nie ma
wartości `zamkniete`: zamknięta pozycja nie jest w backlogu, tylko w historii.

Wzorzec jest wzięty z [`issue-reporting.md`](issue-reporting.md) §9, gdzie
zgłoszenie zamyka przejście kroków reprodukcji, a nie merge. Tu jest tak samo:
zamyka zielona bramka, a nie odhaczone pole.

Odstępstwo zamyka pozycję wyłącznie z właścicielem, powodem i datą wygaśnięcia.
Po tej dacie pozycja wraca jako otwarta — automatycznie, nie z czyjejś dobrej
woli.

## 6a. Etapy zadania i zmiana tematu

Agent główny utrwala przyjęte nietrywialne zobowiązanie przed pracą, a stan
przy przełączeniu tematu i zakończeniu etapu. Nie zapisuje każdej wypowiedzi.
Zobowiązanie wieloetapowe lub wykraczające poza bieżącą turę wymaga zapisu.
Dla zadania wieloetapowego lista etapów odbioru istnieje raz: w pozycji
backlogu albo w briefie wskazanym przez `BRIEF`. Przyjęte kryteria i zakres
pozostają punktem odniesienia; ich zmiana wymaga upoważnienia właściciela,
które może już wynikać z rozmowy. Samo pominięcie etapu nie zmienia zakresu.

Sekcja ma nagłówek `## Etapy odbioru` w briefie albo `#### Etapy odbioru`
w pozycji. Jeden wiersz na uzgodniony rezultat, nie na komendę ani próbę:
w sekcji są wyłącznie wiersze etapów; notkę stanu umieść przed nią albo pod
osobnym nagłówkiem tego samego poziomu. Sekcja może kończyć pozycję.

```markdown
## Etapy odbioru
- [x] X1 — odczyt danych | DOWOD: <test lub artefakt>
- [x] X2 — walidacja | DOWOD: <test lub artefakt>
- [ ] X3 — zapis | NASTEPNY_KROK: sprawdzić kontrakt zapisu
- [ ] X4 — odbiór całej ścieżki
```

Przy nowym temacie X pozostaje `w trakcie`, albo zostaje jawnie odłożone
z powodem i następnym krokiem. Nowe ustalenie może zmienić kolejność pracy;
nie kasuje wcześniejszych etapów. Raport wymienia wykonane i pozostałe ID.
Przed zadeklarowaniem ukończenia całego X sprawdza się wszystkie jego etapy
i kryteria odbioru, także po kompaktowaniu i nowej sesji.
Odczyt planu następuje przed „gotowe”, przy handoffie i po wznowieniu;
przy zmianie zakresu review sprawdza odsyłacz do decyzji lub wiadomości
właściciela. Sam zapis agenta „zgoda była” nie potwierdza upoważnienia.

`python3 templates/task-completion.py <plik-planu>` odrzuca otwarte etapy,
pusty plan i wykonany etap bez odsyłacza do dowodu. Dla pozycji backlogu
podaj `--task <ID>`; checker przejdzie do `BRIEF` i odrzuci dwie listy etapów.
Przed zamknięciem wymagane jest porównanie ID i rezultatów z utrwalonym
zakresem: `--baseline-ref <commit>:<ścieżka-planu>` albo `--baseline <plan>`
dla wcześniej zachowanej bazy poza zapisem wykonawcy. Wynik podaje pełny SHA
i ścieżkę wersji gitowej albo hash pliku bazy. Bez bazy zwraca
`SCOPE_UNVERIFIED` i kod niezerowy nawet przy odhaczonych etapach.
Po upoważnionej zmianie zakresu wskazuje się nową bazę, z odsyłaczem do
decyzji. Bazy nie tworzy się dopiero przy zamykaniu zadania. Review sprawdza
jej pochodzenie; sam hash nie potwierdza upoważnienia ani prawdziwości treści.

Wynik `READY_FOR_REVIEW` potwierdza strukturę zapisu, nie prawdziwość dowodów
ani akceptację pracy. Przegląd sprawdza ich związek z etapami i kryteriami;
bramki projektu nadal obowiązują. Zapis w historii i usunięcie rodzica z
backlogu następują dopiero po domknięciu wszystkich wymaganych etapów.

## 7. Czego ta konwencja nie zmienia

- **Nie zmienia, kto pisze do backlogu.** Reguła „najpierw zapisz, potem
  kontynuuj" i tryb `Inbox` dla nieznanego priorytetu zostają bez zmian.
- **Nie zastępuje task-briefu.** Brief nadal jest dla zadań wymagających
  dłuższego kontekstu i nadal ma dokładnie jeden link z backlogu — teraz przez
  pole `BRIEF`.
- **Nie wprowadza szacowania kosztu.** Kolejność ustala właściciel; automatyczna
  estymacja bez danych historycznych to zgadywanie udające liczbę.

## 8. Egzekwowanie

**Blokują:**

- pozycja bez kompletu kluczy z §2;
- identyfikator niezgodny ze wzorcem albo powtórzony;
- `STATUS: zaparkowane` lub odstępstwo bez `PRZEGLAD`;
- `PRZEGLAD` z datą przeszłą — wyjątek po terminie;
- `BRIEF` wskazujący nieistniejący plik;
- pozostawiony marker `TODO:` po migracji.

**Raportują:**

- wiek najstarszej pozycji o wpływie `high` (uzupełnia punkt 14i kontroli głębokiej);
- liczba pozycji bez bramki, czyli zamykalnych wyłącznie odstępstwem;
- pozycje w `## Poza kolejką`, którym `PRZEGLAD` wypada w ciągu 7 dni.

Narzędzie: [`templates/backlog-lint.sh`](../templates/backlog-lint.sh) — działa
bez konfiguracji projektu, tak samo jak pozostałe szablony bramek.

## 9. Sygnały maszynowe

| Sygnał | Znaczenie |
|---|---|
| `BACKLOG_ITEMS` | liczba pozycji; skok w górę bez audytu = ktoś sypie do backlogu zamiast pracować |
| `BACKLOG_MALFORMED` | pozycje niezgodne z kontraktem; niezerowe blokuje |
| `BACKLOG_OVERDUE_REVIEWS` | odstępstwa po terminie — wracają jako otwarte |
| `BACKLOG_OLDEST_HIGH_DAYS` | wiek najstarszej pozycji `high`; rośnie monotonicznie = kolejka jest fikcją |
| `BACKLOG_ORPHAN_BRIEFS` | briefy bez linku z backlogu |
| `BACKLOG_NO_GATE` | pozycje bez bramki zamykającej |

Powiązane: [`project-state-layout.md`](project-state-layout.md),
[`context-budget.md`](context-budget.md),
[`issue-reporting.md`](issue-reporting.md),
[`test-evidence.md`](test-evidence.md),
[`change-provenance.md`](change-provenance.md),
[`quality-gates-and-dod.md`](quality-gates-and-dod.md),
[`rules-as-gates.md`](rules-as-gates.md).
