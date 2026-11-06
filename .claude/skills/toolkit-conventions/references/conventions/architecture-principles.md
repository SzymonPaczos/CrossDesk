# Konwencja: zasady naczelne architektury

Stack-agnostic. **Dokument nadrzędny pakietu architektonicznego** — ustanawia
wspólne kryteria projektowe, słownik granic i format wyjątku, do którego
odwołują się pozostałe konwencje architektoniczne.

Nie określa frameworka, nazw katalogów ani konfiguracji narzędzi.

## Jak czytać reguły

- **MUSI** — warunek konieczny. Odstępstwo wymaga formalnego wyjątku.
- **NIE WOLNO** — zakaz. Wyjątek musi być lokalny, czasowy i jawny.
- **POWINIEN** — zasada domyślna. Odstępstwo wymaga uzasadnienia w PR.
- **MOŻE** — dopuszczalna technika, jeżeli nie narusza silniejszych reguł.

Trzy granice, którymi operuje cały pakiet:

- **Granica zmiany** — miejsce, którego elementy zwykle zmieniają się razem i
  z tego samego powodu.
- **Granica zaufania** — punkt wejścia danych niekontrolowanych: HTTP, webhook,
  kolejka, plik, CLI.
- **Granica runtime/bundla** — przejście między klientem, serwerem, workerem,
  skryptem i testem.

**Priorytet w razie konfliktu reguł:** bezpieczeństwo i integralność danych →
poprawność domenowa i kontrakty → granice runtime i zależności → testowalność i
obserwowalność → wygoda i skrócenie kodu.

## Reguły

- Każdy moduł, komponent, endpoint i przypadek użycia MUSI mieć jedną
  dominującą granicę zmiany.
- Dane przekraczające granicę zaufania MUSZĄ zostać zwalidowane przed wejściem
  do logiki domenowej.
- Zależności MUSZĄ wskazywać w stronę bardziej stabilnych reguł. Domena NIE
  MOŻE zależeć od transportu, frameworka ani bazy.
- Źródło prawdy dla danych MUSI być jedno i jawne.
- Decyzje nieodwracalne lub kosztowne MUSZĄ być podejmowane przy granicy
  przypadku użycia, a nie ukryte w helperze.
- Abstrakcja, cache, memoizacja i współdzielony moduł POWINNY rozwiązywać
  wykazany problem, nie hipotetyczną przyszłość.
- Najmniejsza poprawna zmiana jest preferowana wobec „porządkowania przy okazji”.
- Reguły MOGĄ być zaostrzone w obszarach wysokiego ryzyka, np. `payments`,
  `identity` lub `security`.

## Test decyzji projektowej

Przed dodaniem warstwy, klasy, komponentu lub abstrakcji autor odpowiada:

1. Jaki konkretny powód zmiany izoluje ta granica?
2. Kto jest właścicielem danych i efektów ubocznych?
3. Czy zależność wskazuje w dozwolonym kierunku?
4. Czy prostsza duplikacja byłaby tańsza od przedwczesnego kontraktu?
5. Jak zostanie przetestowana awaria, a nie tylko ścieżka sukcesu?

## Wyjątki

Wyjątek od MUST jest dopuszczalny wyłącznie z właścicielem, uzasadnieniem,
ryzykiem, ograniczeniem ryzyka, identyfikatorem zadania i datą wygaśnięcia.
Wyjątki NIE MOGĄ omijać walidacji wejścia, kontroli dostępu, ochrony sekretów
ani integralności operacji krytycznych.

```yaml
convention-exception:
  rule: "code-structure.md#cykle"
  reason: "Tymczasowa zgodność z modułem legacy"
  risk: "Niejawna zależność warstw"
  mitigation: "Ograniczenie do dwóch wskazanych modułów"
  owner: "@team-platform"
  tracking: "ARCH-1234"
  expires: "2026-10-31"
```


## Reguła adopcji

Nowy kod MUSI spełniać reguły od początku. Kod istniejący jest poprawiany
metodą „boy scout" w zmienianym obszarze, ale PR NIE POWINIEN zamieniać
lokalnej zmiany w migrację całego systemu. Nowa bramka dla repozytorium legacy
najpierw działa raportowo, z ustaloną datą migracji, i dopiero potem blokuje —
procedura w [`rules-as-gates.md`](rules-as-gates.md).


## Egzekwowanie: rozstrzyga czytanie

**Tej reguły nie egzekwuje żaden skrypt.** Skala MUSI/NIE WOLNO/POWINIEN/MOŻE, pięć pytań testu decyzji projektowej i kolejność priorytetów przy konflikcie reguł rozstrzygają się w rozmowie z właścicielem, nie greperm. Sprawdzalny mechanicznie jest wyłącznie kształt wyjątku (`convention-exception` z niewygasłym polem `expires`) — i to jest kandydat do koszyka `bramka`, a nie cała ta konwencja.

W rejestrze reguł (`templates/rejestr-regul.sh`)
ta konwencja stoi w koszyku `czytanie` i pokazuje się w raporcie audytu jako
CZYTANA — czyli reguła, która stoi na czyimś słowie, a nie na kodzie wyjścia.
Zapisane jest to jawnie, bo reguła wyglądająca na egzekwowaną, a nieegzekwowana,
jest dokładnie tą miękkością, o którą chodzi: brzmi tak samo stanowczo jak
`code-structure.md`, a nikt jej nie sprawdza.

Zmiana tego stanu wymaga napisania bramki i przeniesienia wiersza do koszyka
`bramka` w tym samym commicie. Dopóki tego nie ma, „MUSI" w tym pliku znaczy
„MUSI, a sprawdzi to człowiek".

Powiązane: [`rules-as-gates.md`](rules-as-gates.md),
[`project-state-layout.md`](project-state-layout.md) (gdzie mieszka rejestr
decyzji i wyjątków).
