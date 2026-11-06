# Konwencja: komunikacja agenta

Zakres: rozmowa z użytkownikiem, raport z zadania i komentarze w kodzie.
Cel: użytkownik rozumie wynik i jego znaczenie, widzi dowody i wie,
czy potrzebna jest jego decyzja.

## 1. Treść i język

Odpowiedź podaje na początku najważniejszy wynik albo informację, o którą
pyta użytkownik. Wyjaśnienie łączy przyczynę z jej skutkiem dla użytkownika.
Przykład, jeśli jest potrzebny, pokazuje konkretną sytuację:
„Walidacja odrzucała status `denied`, więc odmowa nie trafiała do bazy”.

Język jest prosty, a terminy techniczne precyzyjne. Skrót, którego użytkownik
może nie znać, jest rozwinięty przy pierwszym użyciu. Odpowiedź pomija
pochwały bez informacji (np. „pomyślnie”, „kompleksowo”, „solidnie”),
powtórzenia polecenia i opisy własnej staranności. Długość i układ wynikają
ze złożoności pytania oraz preferencji użytkownika.

## 2. Twierdzenia i dowody

Odpowiedź odróżnia wykonane czynności i obserwacje od wniosków, przypuszczeń
i planów. Istotne twierdzenie o stanie kodu lub wyniku pracy ma wskazaną
podstawę: wynik testu, odczyt kodu, pomiar, obserwację lub źródło. Zakres
twierdzenia odpowiada temu, co sprawdzono. Odczyt kodu nie potwierdza
wykonania programu.

Opis zamierzonego zachowania nie dowodzi jego implementacji. Jeśli
komentarz obiecuje odrzucenie pustego wejścia, a funkcja je przyjmuje,
raport wskazuje tę rozbieżność. Naprawa i wymagane testy nadal podlegają
[`test-evidence.md`](test-evidence.md); opis lub komentarz ich nie zastępuje.

## 3. Komentarze w kodzie

Komentarz krótko wyjaśnia powód, ograniczenie lub decyzję, których nie
widać z kodu. Dokumentacja interfejsu opisuje kontrakt potrzebny odbiorcy,
np. skutki uboczne lub błędy.
Dłuższe uzasadnienie wspólne dla modułu należy do dokumentacji modułu albo
rejestru decyzji. Komentarz pozostaje zgodny z implementacją.

## 4. Założenia i zakres

Agent może zakwestionować założenie na podstawie nowych dowodów. Gdy je
zmienia, informuje o tym użytkownika i podaje powód. Aktualizuje też zapis
według sekcji [„Decyzja, która przestała obowiązywać”](document-claim-drift.md#decyzja-która-przestała-obowiązywać).

Zmiana celu, zawężenie zakresu lub zmiana kryteriów odbioru wymagają
upoważnienia właściciela. Uzasadnienie w commicie nie udziela tej zgody.
Wcześniejsze upoważnienie obowiązuje w swoim zakresie; nie wymaga ponawiania.
Brak decyzji zatrzymuje zależną część zadania, a niezależna praca może trwać.
Granice ról określa [`multi-agent-delivery.md`](multi-agent-delivery.md).

## 5. Raport z pracy

Raport podaje wynik, sposób i rezultat weryfikacji oraz istotne
ograniczenia. Przy niepełnym wykonaniu wskazuje pozostałą pracę i przyczynę;
przy potrzebnej decyzji wyjaśnia, czego brakuje do kontynuacji.
Niewykonana część uzgodnionego zadania pozostaje otwarta.
Przy zmianie tematu i raporcie końcowym zadania wieloetapowego odpowiedź
rozlicza wykonane oraz pozostałe etapy z jednego planu odbioru. „X2 gotowe”
nie oznacza „X gotowe”; nowa wiadomość sama nie anuluje pozostałych etapów.
„Prawie”, „w większości” i „zasadniczo” nie zastępują wskazania pozostałej pracy.

Aktualizacja w trakcie pracy podaje istotne ustalenie, przeszkodę lub
następny krok. Końcowa odpowiedź zawiera informacje potrzebne do oceny
wyniku bez czytania wcześniejszych aktualizacji. Widoczny diff może skrócić
opis zmian; wyniki kontroli i istotne ograniczenia nadal należą do raportu.

## Ocena

Egzekwuje: przegląd treści i wskazanych dowodów przez człowieka, chyba że
projekt jawnie dopuścił innego oceniającego.
Koszyk `czytanie` w `templates/rejestr-regul.sh` określa metodę oceny;
sam status `CZYTANA` nie potwierdza wykonania przeglądu. Zapis przeglądu
wskazuje rzeczywistego oceniającego i sprawdzony materiał. Linter dostarcza
pomocniczych sygnałów językowych.

Powiązane: [`instruction-style.md`](instruction-style.md),
[`ui-copy.md`](ui-copy.md) dla interfejsu,
[`change-provenance.md`](change-provenance.md) dla commitów.
