# Konwencja: składanie stacku — co się łączy, co się wyklucza

Stack-agnostic. Zakres: **jak zapisywać wybór technologii, żeby dało się go
później zrewidować, i które kombinacje są zabronione niezależnie od jakości
składników.**

Rozdział ról:
[`tool-adoption-and-measurement.md`](tool-adoption-and-measurement.md) mówi,
**kiedy wolno wpuścić narzędzie** (statusy dojrzałości, tryb cienia, pomiar);
[`architecture-change.md`](architecture-change.md) — **kiedy wolno zmienić
decyzję**. Ta konwencja mówi, **co z czym może stać obok siebie**.

---

## 1. Wybór bez warunku stosowalności nie jest wyborem

- Każda pozycja stacku MUSI mieć zapisany **warunek stosowalności**: sytuację,
  w której ten wybór jest właściwy. Żadna technologia nie jest właściwa zawsze,
  a zapis „używamy X" bez warunku nie daje się zakwestionować ani potwierdzić.
- Każde **odrzucenie** MUSI mieć zapisany **sygnał powrotu**: obserwację, po
  której decyzja wraca na stół. Odrzucenie bez sygnału powrotu za pół roku
  wygląda jak przeoczenie i ktoś je „naprawi".
- Odrzucenie NIE oznacza „złe". Oznacza: **w tej klasie systemów koszt
  przewyższa zysk**. Ta różnica decyduje, czy zapis przetrwa spotkanie z osobą,
  która danego narzędzia z powodzeniem używa gdzie indziej.

## 2. Reguła wspólna wszystkich wykluczeń

**Dwie rzeczy pełniące tę samą rolę na tych samych danych zawsze się
rozjadą.**

To nie jest ranking jakości — to własność układu. Rozjazd nie następuje przy
wdrożeniu (wtedy oba opisy są zgodne, więc konfiguracja przechodzi review),
tylko przy pierwszej zmianie, której autor nie wiedział, że jest drugi
właściciel. Dlatego wykluczenia rozstrzyga się **przy wyborze**, nie przy
pierwszym incydencie.

## 3. Pary wykluczające się

| Para | Dlaczego się wyklucza | Reguła rozstrzygnięcia |
| --- | --- | --- |
| dwa odwzorowania obiektowo-relacyjne na jednej bazie | dwa opisy jednego schematu; każda zmiana wymaga ręcznej synchronizacji | właścicielem odwzorowania jest ten proces, który jest właścicielem schematu; pozostałe dostają wygenerowane modele i dostęp do wyznaczonych tabel |
| dwa systemy migracji jednej bazy | dwie historie wersji, konflikt nierozstrzygalny automatycznie | jeden właściciel migracji — zawsze ten sam, co właściciel schematu |
| dwa walidatory w jednym języku | dwie semantyki walidacji tego samego kształtu; kanon przestaje być kanonem | jeden walidator na język, generacja między językami — [`contract-canon.md`](contract-canon.md) |
| generacja kontraktu w dwie strony | dwa kierunki to dwa kanony, czyli zero kanonów | kanon tam, gdzie żyje bramka; generacja płynie od niego w jedną stronę |
| dwa kanały strumienia do tego samego klienta | dwie kolejności zdarzeń; rozjazd niemożliwy do odtworzenia w debugowaniu | jeden strumień; zdarzenia innych rodzajów jako typy w tym samym kanale |
| dwie ścieżki autoryzacji tej samej operacji | bramka nie przecieka przez obejście, tylko przez drugą, „prostszą" ścieżkę, w której ktoś zapomni o sprawdzeniu | jedna funkcja autoryzująca; rodzaj danych wybiera wykonawcę zmiany, nigdy ścieżkę autoryzacji |
| dwa źródła prawdy o tym samym fakcie | ten sam fakt w dwóch miejscach rozjeżdża się w tempie zmian | fakt domenowy trzymany u siebie; biblioteka dostaje adapter, nie własność |
| stan w kliencie i na serwerze jako równorzędne | „synchronizacja" bez autorytetu to konflikt bez rozjemcy | serwer jest autorytetem, klient renderuje projekcję, pełny stan nadpisuje klienta |
| instrukcja tekstowa jako kontrola obok mechanizmu jako kontroli | mylenie ról: instrukcja poprawia przypadek średni, mechanizm ogranicza najgorszy | instrukcja = wskazówka, mechanizm = gwarancja; bezpieczeństwo projektuje się na najgorszy przypadek |
| dwa frameworki tej samej warstwy równolegle | każdy niesie własny model stanu, trwałości i błędów; dwa naraz to wszystko podwójnie | jeden na warstwę; wielość realizuje się wewnątrz niego, nie obok niego |

## 4. Kryterium właściciela

Gdy dwie rzeczy pełnią tę samą rolę i obie są potrzebne z innych powodów,
rozstrzyga **kto jest właścicielem danych**, a nie która jest lepsza:

- właścicielem schematu jest jeden proces; pozostałe czytają wygenerowane
  modele;
- właścicielem migracji jest ten sam proces, co właścicielem schematu;
- właścicielem faktu domenowego jest system, nie biblioteka; biblioteka
  dostaje adapter.

Kryterium jakości wraca dopiero **po** rozstrzygnięciu własności — wtedy pyta
się, która implementacja lepiej obsłuży rolę, a nie która wygra spór.

## 5. Zależności open-core i cudza chmura

Zanim zależność trafi na ścieżkę krytyczną, MUSZĄ paść trzy pytania:

1. **Co przestaje działać bez licencji — i czy przestaje głośno?** Funkcja,
   która cicho degraduje, jest gorsza od takiej, która się nie uruchamia.
2. **Co woła cudzy serwer i czy da się wskazać własny?** Brak możliwości
   wskazania własnego adresu jest twardym wykluczeniem, nie niedogodnością.
3. **Czy trzyma dane będące naszym źródłem prawdy?** Jeśli tak, a własnego
   miejsca wskazać się nie da — odpada niezależnie od licencji.

Weryfikacja MUSI być mechaniczna: przebieg dymny z monitorowaniem ruchu
wychodzącego, na liście dozwolonych wyłącznie jawnie skonfigurowane adresy.
Telemetria bibliotek domyślnie wyłączona — patrz
[`third-party-assets-privacy.md`](third-party-assets-privacy.md).

Znalezisko z jednego komponentu **nie uogólnia się** na całą bibliotekę.
Zakres wykluczenia mierzy się tak samo, jak jego zasadność.

## 6. Egzekwowanie

**Blokują:**

- dwie rzeczy z jednego wiersza tabeli §3 obecne jednocześnie w repozytorium;
- zależność wołająca zewnętrzny adres spoza listy dozwolonych;
- zależność trzymająca źródło prawdy poza systemem.

**Raportują:**

- pozycja stacku bez zapisanego warunku stosowalności;
- odrzucenie bez zapisanego sygnału powrotu;
- nowa zależność bez odpowiedzi na trzy pytania z §5;
- biblioteka z domyślnie włączoną telemetrią.

**Czym to sprawdzić:** [`templates/stan-stosu.sh`](../templates/stan-stosu.sh)
wypisuje inwentarz — co w repozytorium stoi w każdej warstwie, z pozycjami
BRAK włącznie — i przy każdej pozycji stawia werdykt wobec zasad stosu.
Werdykt jest zdaniem („nie używaj Astro w aplikacji — widok ma stać na Next"),
bo raport czyta się bez legendy pod ręką.

Wynik idzie do raportu **w całości, jedna tabela na projekt**. Skrócenie do
odstępstw albo do porównania między projektami niszczy jedyny powód, dla
którego ta tabela istnieje: właściciel czyta ją, żeby sprawdzić stan
konkretnego repozytorium, a nie żeby zobaczyć, co się wyróżnia.

Skrypt **zawsze kończy się kodem 0** i to jest celowe: odstępstwo od zasady
stosu nie jest defektem do naprawienia na miejscu, tylko decyzją do zapisania
z właścicielem i datą przeglądu. Blokują dopiero pozycje z listy powyżej,
i blokują je bramki projektu, nie inwentarz.

## 7. Sygnały maszynowe (tryb raportowy)

1. Dwa pakiety tej samej roli w pliku zależności.
2. Dwa katalogi migracji w jednym repozytorium.
3. Import drugiego walidatora w języku, który ma już kanon.
4. Konfiguracja z adresem zewnętrznym bez odpowiednika w liście dozwolonych.
5. Wpis w rejestrze decyzji o wyborze technologii bez pola warunku.
6. Zmienna środowiskowa telemetrii nieustawiona jawnie.

Powiązane: [`tool-adoption-and-measurement.md`](tool-adoption-and-measurement.md),
[`architecture-change.md`](architecture-change.md),
[`contract-canon.md`](contract-canon.md),
[`third-party-assets-privacy.md`](third-party-assets-privacy.md),
[`architecture-principles.md`](architecture-principles.md).
