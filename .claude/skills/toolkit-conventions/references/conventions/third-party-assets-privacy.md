# Konwencja: zasoby zewnętrzne w aplikacji a prywatność użytkownika

Stack-agnostic. Zakres: **fonty, ikony, style, biblioteki i osadzenia ładowane
z cudzych serwerów w czasie działania aplikacji** — dlaczego to jest
przetwarzanie danych osobowych, kiedy jest bezpodstawne i jak zamienić regułę
w mechaniczny gate.

To nie jest porada prawna. To standard techniczny z uzasadnieniem i odsyłaczami
do źródeł. Kwalifikację prawną konkretnego transferu, wybór podstawy, test
uzasadnionego interesu i przekazanie poza EOG uzgadnia się z prawnikiem lub IOD.

## 1. Mechanizm: co się dzieje przy jednym `<link>`

Przeglądarka, pobierając zasób z cudzej domeny, **sama** wysyła do tego
serwera adres IP użytkownika, `User-Agent`, `Referer` (czyli adres
odwiedzanej podstrony), a często nagłówki językowe i `Sec-CH-UA`. Dzieje się
to zanim użytkownik cokolwiek kliknie i niezależnie od tego, czy odrzucił
banner zgód.

Kluczowe jest to, **kto to robi**: nie użytkownik odwiedza dostawcę — to my
kierujemy jego przeglądarkę na cudzy serwer. Profilowanie wykonane cudzymi
rękami pozostaje profilowaniem wykonanym z naszej inicjatywy.

Nie zakładaj, że „brak ciasteczek" znaczy „brak przetwarzania danych". Samo
żądanie ujawnia komplet danych technicznych, a EROD w wytycznych 2/2023
wskazuje, że w zakres art. 5 ust. 3 dyrektywy ePrivacy mogą wchodzić również
techniki bezciasteczkowe — instrukcje JavaScript wysyłające żądanie,
śledzące adresy URL, pixele i część mechanizmów opartych na adresie IP.

## 2. Podstawa: zasady, nie jeden wyrok

Regułę niosą przede wszystkim **zasady RODO**, nie orzecznictwo krajowe:

- **minimalizacja danych** (art. 5 ust. 1 lit. c) — przetwarzasz to, co
  niezbędne do celu;
- **ochrona danych w fazie projektowania i domyślnie** (art. 25) —
  konfiguracja domyślna ma być najbardziej chroniąca prywatność;
  EROD w wytycznych 4/2019 zaleca wyłączanie funkcji zewnętrznego
  oprogramowania, które nie mają podstawy prawnej lub nie odpowiadają celowi.

Adres IP jest **danymi osobowymi** — TSUE przesądził to w sprawie *Breyer*
(C-582/14) dla dynamicznego adresu IP, o ile istnieją legalne środki
pozwalające powiązać go z osobą. UODO w swoich materiałach odwołuje się do tej
szerokiej definicji, więc w praktyce polskiej projektuj tak, jakby adres IP i
identyfikatory internetowe **były** danymi osobowymi.

**Test konieczności** — najbardziej użyteczna część niemieckiego orzecznictwa.
LG München I (wyrok z 20.01.2022, sygn. 3 O 17493/20) uznał dynamiczne
osadzenie Google Fonts bez zgody za naruszenie RODO i zasądził 100 EUR wraz z
zakazem dalszego przekazywania IP. Sedno uzasadnienia uogólnia się na dowolny
zasób: uzasadniony interes odpada, **ponieważ font można było hostować
lokalnie** — transfer był niekonieczny.

Uczciwe zastrzeżenia, bo ten wyrok bywa nadużywany w obie strony:

- to orzeczenie sądu pierwszej instancji w jednym państwie członkowskim, nie
  precedens obowiązujący w całej UE i nie wyrok TSUE;
- wywołało falę masowych wezwań do zapłaty, którą kolejne sądy uznały za
  **nadużycie prawa**, oddalając roszczenia seryjnych żądających (m.in. LG
  Baden-Baden 11.10.2022, sygn. 3 O 277/22; AG Berlin-Charlottenburg
  20.12.2022, sygn. 217 C 64/22; AG Ludwigsburg 28.02.2023, sygn. 8 C 1361/22);
- realnym ryzykiem nie jest więc żądanie 100 EUR od przypadkowej osoby, tylko
  **skarga do organu nadzorczego** i postępowanie z jego inicjatywy, plus koszt
  reputacyjny w projekcie deklarującym prywatność.

Wniosek praktyczny jest niezależny od orzecznictwa: transfer, którego można
uniknąć jednym poleceniem builda, jest ryzykiem bez korzyści.

## 3. Polityka w formie wymagań

- **MUST** — fonty, ikony, style, podstawowe skrypty i elementy design systemu
  są serwowane z własnego originu.
- **MUST** — każde żądanie runtime do obcej domeny ma właściciela, cel,
  podstawę prawną i wpis w rejestrze zasobów zewnętrznych (§10).
- **MUST NOT** — zakładać, że „brak ciasteczek" oznacza „brak przetwarzania
  danych".
- **SHOULD** — zależności instaluje się z menedżera pakietów **podczas
  builda**, ale ich kod i assety dostarcza użytkownikowi własny serwer.
- **SHOULD** — CSP domyślnie blokuje domeny spoza allowlisty.
- **MAY** — zewnętrzny CDN wyłącznie wtedy, gdy daje udokumentowaną korzyść i
  przeszedł analizę prywatności, bezpieczeństwa oraz przekazania danych.

Samo użycie CDN nie jest automatycznie nielegalne. Problemem jest to, że
przeglądarka użytkownika łączy się z dodatkowym podmiotem — więc ciężar
uzasadnienia leży po stronie tego, kto chce ten transfer utrzymać.

## 4. Decyzja per klasa zasobu

| Zasób | Domyślnie | Wyjątek |
|---|---|---|
| Font | lokalny WOFF2 | brak praktycznej potrzeby CDN |
| Ikona | lokalny komponent SVG lub sprite | zewnętrzny zestaw tylko po analizie |
| CSS frameworka | bundlowany lokalnie | brak praktycznej potrzeby CDN |
| Biblioteka JS | bundlowana lokalnie | CDN z CSP i SRI, jeśli uzasadnione |
| Analityka | wyłączona do czasu rozstrzygnięcia zgody, jeśli zgoda jest wymagana | tryb bezciasteczkowy tylko po analizie technicznej i prawnej |
| Wideo, mapa, widget | **fasada** aktywowana świadomym działaniem użytkownika | bezpośrednie osadzenie tylko po analizie |

„Fasada" to statyczny podgląd (miniatura, zrzut mapy) z przyciskiem; dopiero
kliknięcie ładuje właściwy widget. Rozwiązuje jednocześnie prywatność i
wydajność.

**Subresource Integrity nie rozwiązuje problemu prywatności.** SRI chroni przed
podmianą treści, nie przed ujawnieniem IP — żądanie i tak wychodzi. Gdy wyjątek
zostanie zatwierdzony, SRI (`integrity` + `crossorigin`) jest mimo wszystko
wymagane.

**Zgoda jest gorszym rozwiązaniem niż self-hosting.** Zgoda na font oznacza
banner przed pierwszym renderem, ścieżkę dla odmowy i interfejs działający bez
tego zasobu. Self-hosting usuwa problem, zamiast go proceduralizować.

## 5. Fonty

Kolejność preferencji:

1. **Fonty systemowe** — zero żądań, zero licencji, natychmiastowy render.
2. **Self-hosting** — pliki w repozytorium lub buildzie, `@font-face`
   wskazujący własną domenę. Praktycznie: paczki npm z fontami (np. Fontsource)
   przy buildzie albo ręcznie pobrane WOFF2 przy prostej stronie. Dostawcy
   katalogów fontów zwykle wprost dopuszczają pobranie do self-hostingu i
   opisują, że wtedy nie otrzymują danych o odwiedzinach.
3. **Usługa bez logowania w UE** jako zamiennik drop-in — lepsze niż globalny
   dostawca reklamowy, ale **wciąż podmiot trzeci**. Etap przejściowy, nie cel.

Przy self-hostingu:

- **WOFF2** jako format domyślny; starsze formaty tylko gdy wymaga tego
  macierz przeglądarek;
- ogranicz liczbę rodzin (zwykle jedna tekstowa, opcjonalnie jedna display) i
  grubości (dwie–trzy);
- **sprawdź polskie znaki** — `ąćęłńóśźż` wraz z wersalikami — przed
  zatwierdzeniem kroju, i wybierz subset `latin-ext`;
- `unicode-range`, gdy dostarczasz kilka rzeczywistych subsetów;
- `font-display` wybierz świadomie: `swap` pokazuje fallback natychmiast, ale
  może wywołać przesunięcie; `optional` maksymalizuje stabilność;
- `size-adjust`, `ascent-override`, `descent-override`, `line-gap-override`,
  gdy podmiana fallbacku powoduje przeskok layoutu;
- **preload tylko fontu krytycznego** dla pierwszego widoku, z atrybutem
  `crossorigin` (wymagany również przy pobraniu anonimowym); nadmiar
  preloadów odbiera priorytet innym zasobom;
- font wariabilny tylko wtedy, gdy naprawdę używasz wielu osi lub grubości.

**Licencję sprawdza się dla konkretnego kroju, nie dla katalogu.** Duże
katalogi mieszają SIL OFL, Apache-2.0 i licencje własne; kroje komercyjne bywają
licencjonowane per domena lub per odsłona. Redystrybucja z własnego serwera musi
być dozwolona, a plik licencji trafia do repozytorium obok fontu.

## 6. Ikony

**Preferuj SVG nad font ikonowy.** Font ikonowy to jeden blob bez sensownego
podziału, gorzej współpracuje z `font-display`, potrafi powodować przesunięcia
layoutu, a fallback może przekazać zupełnie inne znaczenie. SVG podlega
tree-shakingowi i jest lepsze dostępnościowo.

Kolejność preferencji:

1. pojedyncze komponenty SVG z lokalnej paczki npm;
2. własne komponenty SVG w repozytorium;
3. first-party sprite SVG;
4. font ikonowy tylko dla starszych integracji;
5. zewnętrzny zestaw ładowany runtime — wyłącznie jako zatwierdzony wyjątek.

Zestawy o liberalnej licencji i dystrybucji paczkowej: **Iconoir** (MIT),
**Lucide** (ISC), **Tabler Icons** (MIT) i inne o tym samym modelu. Kryterium
wyboru jest zawsze to samo: **licencja pozwalająca na redystrybucję i
dystrybucja jako paczka, nie jako URL**.

Dwie pułapki techniczne przy przenoszeniu ikon do siebie:

- **Sprite `<use>` musi być same-origin.** Przeglądarki odrzucają odwołania
  cross-origin w `href` elementu `<use>`, a dla tego elementu nie ma
  zdefiniowanego sposobu ustawienia polityki cross-origin.
- **Nie zgub dostępności przy okazji.** Ikona dekoracyjna dostaje
  `aria-hidden="true"` i `focusable="false"`, ale `aria-hidden` nigdy nie trafia
  na fokusowalny przycisk. Przycisk z samą ikoną musi mieć dostępną nazwę —
  widoczną etykietę, `aria-label` albo `aria-labelledby`.

## 7. Generatory fontów ikonowych — rozróżnienie build-time i runtime

Narzędzia typu Fontello są **generatorami build-time**: wybierasz glify,
pobierasz archiwum z fontem, CSS-em i informacją licencyjną, hostujesz całość u
siebie. Przy lokalnym wdrożeniu **nie istnieje żaden „runtime" takiego
narzędzia** i przeglądarka użytkownika nie łączy się z jego domeną.

Trzeba jednak rozdzielić trzy rzeczy, bo mieszanie ich prowadzi do fałszywych
zarzutów albo do fałszywego spokoju:

1. **Prywatność użytkownika** — lokalny font i lokalny CSS nie generują żądania
   do dostawcy narzędzia. To jest w porządku.
2. **Przepływ danych dewelopera** — konfiguracja zestawu jest wysyłana na
   serwer narzędzia w trakcie pracy, a sesja bywa tam przechowywana (w
   przypadku Fontello: przez dobę). Dotyczy zespołu, nie użytkownika, ale
   należy o tym wiedzieć.
3. **Licencje** — kod generatora bywa na MIT, natomiast **ikony wejściowe mogą
   być na SIL OFL, CC BY albo CC BY-SA**. Wygenerowany `LICENSE.txt` zostaje w
   repozytorium, a obowiązki wobec autorów ikon trzeba spełnić.

Reguła ogólna dla każdego narzędzia tej klasy: **build-time w porządku, runtime
z cudzej domeny nie.**

## 8. Nagłówki

**CSP** jest jedynym mechanizmem działającym również na zasoby dokładane
dynamicznie w przeglądarce. Punkt startowy do dopasowania, nigdy do wklejenia
bez testu:

```
Content-Security-Policy:
  default-src 'self';
  base-uri 'self';
  object-src 'none';
  frame-ancestors 'none';
  font-src 'self';
  img-src 'self' data:;
  style-src 'self';
  script-src 'self';
  connect-src 'self';
  form-action 'self';
```

Aplikacja z inline styles, nonce, workerami, WebSocketami, płatnościami lub
osadzonymi usługami wymaga świadomej konfiguracji. Wdrażaj przez
`Content-Security-Policy-Report-Only`, zbierz naruszenia, usuń nieoczekiwane
zależności, dopiero potem egzekwuj — to jest wprost krok 3 z
[`rules-as-gates.md`](rules-as-gates.md).

Uzupełniająco:

```
Referrer-Policy: no-referrer
Permissions-Policy: geolocation=(), microphone=(), camera=(), local-fonts=()
X-Content-Type-Options: nosniff
```

`Referrer-Policy` ogranicza to, ile o odwiedzanej podstronie trafia do
odbiorcy żądania. `Permissions-Policy` wyłącza nieużywane API — dyrektywa
`local-fonts` ogranicza dostęp do listy fontów zainstalowanych na urządzeniu
użytkownika, czyli do sygnału wprost nadającego się do fingerprintingu.

## 9. Gate

Reguła prozą nie przetrwa pierwszego „szybko dodam jeszcze jeden font".
Kolejność wdrożenia zgodnie z [`rules-as-gates.md`](rules-as-gates.md):

**Poziom 1 — grep w źródłach (natychmiast, blokująco).** Odwołania do
zewnętrznych hostów w szablonach, arkuszach stylów i konfiguracji: `//fonts.`,
`cdn.`, `//ajax.`, `unpkg`, `jsdelivr`, `cdnjs`, `gravatar`,
`youtube.com/embed`, `google.com/recaptcha`, `googletagmanager`. Trafienie
blokuje z instrukcją; wyjątki jako jawna allowlista w repozytorium, z
uzasadnieniem przy każdej pozycji.

**Poziom 2 — grep w artefakcie builda (blokująco).** To samo na wyjściu:
zależność potrafi wstrzyknąć zewnętrzny URL, którego nie ma w naszym kodzie.
Ten poziom łapie klasę „nie my to dodaliśmy".

**Poziom 3 — CSP, najpierw raportowo** (§8).

**Poziom 4 — weryfikacja na uruchomionej aplikacji (okresowo).** Załaduj
kluczowe widoki i wypisz listę domen, do których poszły żądania. Jedyna metoda
odporna na zasoby dokładane warunkowo. Naturalne miejsce: ten sam etap, na
którym działa DAST — patrz
[`security-verification-gates.md`](security-verification-gates.md).

## 10. Rejestr zasobów zewnętrznych

Projekt utrzymuje listę **wszystkich** świadomie dopuszczonych podmiotów
trzecich działających w przeglądarce użytkownika: nazwa, cel, kategorie danych,
podstawa prawna, lokalizacja przetwarzania, właściciel decyzji, data przeglądu.

Ta lista jest jednocześnie źródłem sekcji polityki prywatności i wejściem do
przeglądu. **Polityka prywatności ma odpowiadać rzeczywistym żądaniom
sieciowym** — rozjazd między nią a zakładką Network jest samodzielnym
problemem. Pozycja bez właściciela i daty przeglądu jest długiem, nie decyzją.

## 11. Licencje i łańcuch dostaw assetów

- Każdy font, zestaw ikon, ilustracja i szablon ma zapisane źródło, wersję,
  datę pobrania i licencję — wersjonowane **razem z assetem**.
- Pliki `LICENSE` i `NOTICE` oraz wymagane atrybucje zostają w repozytorium.
- **Logotypy i ikony marek to znaki towarowe, nie zwykłe ikony** — licencja
  zestawu ikon nie daje prawa do używania cudzego logo.
- Build nie pobiera plików z internetu bez lockfile'a i kontroli integralności.
- CI generuje raport licencji lub SBOM — szczegóły w [`ci-cd.md`](ci-cd.md).

## 12. Gotowy blok do `CONTRIBUTING.md`

> 1. Produkcja nie ładuje fontów, ikon, stylów ani bibliotek JS z publicznych CDN-ów.
> 2. Zależność może być pobrana podczas builda, ale runtime serwuje bundle first-party.
> 3. Każda nowa domena widoczna w zakładce Network wymaga przeglądu prywatności i bezpieczeństwa.
> 4. Każdy asset ma zapisaną licencję w repozytorium.
> 5. CSP jest testowana w CI/staging i egzekwowana na produkcji.
> 6. Wyjątki od standardu mają właściciela, uzasadnienie i datę ponownego przeglądu.

## 13. Sygnały maszynowe (tryb raportowy)

1. Zewnętrzny host zasobu w źródłach lub w artefakcie builda spoza allowlisty.
2. Brak nagłówka CSP albo CSP z `*` w `font-src`/`script-src`.
3. Pozycja w rejestrze zasobów bez podstawy prawnej lub po terminie przeglądu.
4. Zasób zewnętrzny ładowany **przed** rozstrzygnięciem zgody, gdy podstawą ma
   być zgoda.
5. Font lub zestaw ikon w repozytorium bez dołączonego pliku licencji.
6. Osadzenie wideo lub mapy bez fasady i bez wariantu ograniczającego śledzenie.
7. `<use>` w sprite SVG wskazujący na inny origin.

## 14. Kolejność wdrożenia w istniejącej aplikacji

1. **Fonty i ikony** — zwykle jedno popołudnie, zero zmian w interfejsie,
   największy udział żądań zewnętrznych.
2. **Biblioteki z publicznych CDN-ów** — przenieś do bundla.
3. **Osadzenia** — fasada albo wariant ograniczający śledzenie.
4. **Analityka i CAPTCHA** — najtrudniejsze, bo dotykają funkcji produktu;
   decyzja jest biznesowa i musi trafić do rejestru.
5. **CSP raportowo → blokująco**, gdy lista zgłoszeń jest pusta.

Krok 1 wykonaj bezwarunkowo. Jest tani, odwracalny i usuwa najczęściej
podnoszony zarzut, zanim ktokolwiek go podniesie.

## Źródła referencyjne

- RODO: art. 5 (zasady) i art. 25 (ochrona danych w fazie projektowania i
  domyślnie) — [tekst
  rozporządzenia](https://eur-lex.europa.eu/legal-content/PL/TXT/?uri=CELEX%3A32016R0679)
- EROD: [Guidelines 4/2019 on Article 25 Data Protection by Design and by
  Default](https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-42019-article-25-data-protection-design-and_en)
- EROD: [Guidelines 2/2023 on Technical Scope of Art. 5(3) of ePrivacy
  Directive](https://www.edpb.europa.eu/our-work-tools/documents/public-consultations/2023/guidelines-22023-technical-scope-art-53-eprivacy_en)
- TSUE: [C-582/14
  *Breyer*](https://gdprhub.eu/index.php?title=CJEU_-_C-582/14_-_Patrick_Breyer)
  — dynamiczny adres IP jako dane osobowe
- LG München I, 20.01.2022, sygn. 3 O 17493/20 —
  [omówienie](https://www.dr-datenschutz.de/schadensersatz-urteil-google-fonts-und-die-dsgvo/)
- Późniejsze orzeczenia o nadużyciu prawa w falach wezwań —
  [omówienie](https://www.brak.de/newsroom/news/abmahnwelle-war-rechtsmissbraeuchlich/)
- Google Fonts: [FAQ, sekcja prywatności](https://fonts.google.com/faq)
- [Iconoir](https://iconoir.com/) (MIT), [Lucide](https://lucide.dev/) (ISC),
  [Tabler Icons](https://tabler.io/icons) (MIT)
- MDN:
  [@font-face](https://developer.mozilla.org/en-US/docs/Web/CSS/@font-face),
  [Content Security
  Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP),
  [Referrer-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy),
  [Permissions-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Permissions-Policy),
  [SVG
  `<use>`](https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/use)

Powiązane: [`rules-as-gates.md`](rules-as-gates.md),
[`ci-cd.md`](ci-cd.md) oraz
[`security-verification-gates.md`](security-verification-gates.md).
