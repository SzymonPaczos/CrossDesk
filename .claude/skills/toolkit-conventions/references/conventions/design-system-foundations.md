# Konwencja: fundamenty design systemu i dostępność

Stack-agnostic w warstwie zasad, z przykładami w CSS. Zakres: **tokeny,
paleta, typografia, stany komponentów i dostępność jako wymaganie, nie
opcja.**

Rozdział ról:

- [`third-party-assets-privacy.md`](third-party-assets-privacy.md) — skąd biorą
  się fonty i ikony, których używa design system.
- [`rules-as-gates.md`](rules-as-gates.md) — awans reguły na gate.
- [`ci-cd.md`](ci-cd.md) — lockfile, raport licencji, SBOM.

## 1. Design system to kontrakt, nie katalog komponentów

Katalog komponentów jest skutkiem. Kontraktem są **tokeny i udokumentowane
zachowanie**: co znaczy „kolor akcji", jak wygląda focus, co się dzieje w
stanie disabled. Bez tego dwa zespoły zbudują dwa różne produkty z tych
samych komponentów.

Praktyczna konsekwencja: **źródłem prawdy są tokeny, nie plik projektowy i
nie implementacja jednego komponentu.**

## 2. Trzy warstwy tokenów

| Warstwa | Rola | Przykład |
|---|---|---|
| primitive | surowa wartość, bez znaczenia | `color.blue.500`, `spacing.2` |
| semantic | intencja w interfejsie, miejsce themingu | `color.action.primary`, `color.text.muted` |
| component | użycie w konkretnym komponencie | `button.primary.bg.hover` |

Reguła, która niesie całą wartość tego podziału: **token komponentu wskazuje
na token semantyczny, nigdy na wartość surową.** Dzięki temu tryb ciemny i
tryb wysokiego kontrastu zmieniają **mapowanie intencji**, a nie każdy
komponent z osobna.

Minimalny zakres:

| Grupa | Minimalny zestaw |
|---|---|
| Kolor | canvas, surface, text, border, action, focus, success, warning, danger |
| Typografia | family, size, weight, line-height, letter-spacing |
| Spacing | zamknięta skala, np. 0, 1, 2, 3, 4, 6, 8, 12, 16 |
| Rozmiary | container, measure, wysokość kontrolki, rozmiar ikony |
| Radius | none, sm, md, lg, pill |
| Elevation | 0–4, każda wartość z opisem zastosowania |
| Z-index | base, dropdown, sticky, overlay, modal, toast |
| Motion | duration fast/normal/slow oraz easing |
| Breakpoints | wynikające z layoutu, nie z modeli urządzeń |

**Skala ma być zamknięta.** Nadmiar arbitralnych wartości spowalnia
projektowanie i psuje komunikację projektant–programista; wyjątek wymaga
komentarza i zatwierdzenia w przeglądzie.

## 3. Theming przez media features, nie przez klasę na `body`

```css
:root {
  /* primitive */
  --blue-500: oklch(55% 0.18 250);
  --neutral-0: oklch(100% 0 0);
  --neutral-900: oklch(20% 0.01 250);

  /* semantic */
  --color-bg-surface: var(--neutral-0);
  --color-text-primary: var(--neutral-900);
  --color-action-primary: var(--blue-500);
  --color-focus-ring: var(--blue-500);

  --space-2: 0.5rem;
  --radius-md: 0.5rem;
  --motion-normal: 200ms;
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-bg-surface: oklch(22% 0.01 250);
    --color-text-primary: oklch(94% 0.005 250);
    --color-action-primary: oklch(72% 0.14 250);
  }
}

@media (prefers-reduced-motion: reduce) {
  :root { --motion-normal: 0ms; }
}
```

`prefers-color-scheme`, `prefers-contrast` i `prefers-reduced-motion` to
preferencje **zadeklarowane przez użytkownika na poziomie systemu**.
Zignorowanie ich jest świadomym nadpisaniem cudzej decyzji.

Format wymiany tokenów (DTCG) bywa użyteczny przy eksporcie na wiele
platform, ale pozostaje raportem grupy roboczej, nie standardem — dopóki
projekt ma jedną platformę, własny prosty schemat JSON plus generator CSS są
tańsze i stabilniejsze.

## 4. Budowa palety — metoda

1. Wybierz jeden kolor akcentowy wynikający z marki lub funkcji.
2. Zbuduj neutralną rampę powierzchni i tekstu.
3. Zbuduj rampę akcentu, zmieniając **głównie jasność**.
4. Dodaj osobne kolory semantyczne: danger, warning, success, info.
5. Przypisz wartości surowe do ról semantycznych.
6. Zdefiniuj każdą rolę w wariancie jasnym, ciemnym i wysokokontrastowym.
7. Przetestuj **wszystkie** pary tekst–tło i komponent–stan.
8. Sprawdź interfejs bez koloru i z symulacją zaburzeń widzenia barw.

OKLCH jest wygodne do budowania ramp, bo `L` opisuje postrzeganą jasność, `C`
chromę, a `H` odcień — zmiana jednej osi nie rozjeżdża pozostałych.

**Ale jasność w OKLCH nie jest testem dostępności.** WCAG liczy kontrast z
luminancji względnej według własnego wzoru. Równe `L` nie oznacza zgodności,
a różne `L` nie oznacza jej braku. Kontrast mierzy się narzędziem, nie okiem
i nie arytmetyką odcieni.

## 5. Dostępność jako wymaganie

Progi z WCAG 2.2 (kryteria 1.4.1, 1.4.3, 1.4.11):

- tekst zwykły: **minimum 4.5:1**;
- tekst duży: **minimum 3:1**;
- istotne obramowania kontrolek, ikony informacyjne i stany: **minimum 3:1**
  względem sąsiadujących kolorów;
- **progów nie wolno zaokrąglać** — 4.499:1 nie spełnia 4.5:1;
- **kolor nie może być jedynym nośnikiem** statusu ani instrukcji.

Focus:

```css
:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}
```

Cel praktyczny to obrys co najmniej 2 px CSS i kontrast 3:1 (kryterium
Focus Appearance na poziomie AAA); na poziomie AA element z fokusem nie może
być całkowicie zasłonięty przez treść autora. Usunięcie `outline` bez
zamiennika jest błędem dostępności, nie decyzją estetyczną.

## 6. Stany komponentów

Każdy komponent interaktywny ma **udokumentowane i przetestowane**: default,
hover, focus-visible, active, selected, disabled, loading, error oraz — jeśli
dotyczy — success.

Dwie reguły, które psują się najczęściej:

- **Disabled nie tłumaczy, dlaczego akcja jest niedostępna.** Wyłączony
  przycisk bez widocznego komunikatu zostawia użytkownika bez wyjścia; podaj
  powód lub powiązany komunikat.
- **Komponent nie ustala własnego marginesu zewnętrznego** zależnego od
  strony, na której jest użyty. Odstęp należy do układu, nie do komponentu.

Zasada bliskości w układzie: odstęp wewnątrz grupy jest mniejszy niż odstęp
między grupami, a odstęp nagłówka od jego treści mniejszy niż od poprzedniej
sekcji.

## 7. Typografia

Role zamiast dowolnych wartości:

| Rola | Typowy zakres | Line-height |
|---|---|---|
| Display | 48–80 px | 1.05–1.15 |
| H1 | 32–48 px | 1.1–1.2 |
| H2 | 24–32 px | 1.15–1.25 |
| H3 | 20–24 px | 1.2–1.3 |
| Body | 16–18 px | 1.5–1.65 |
| Label | 14–16 px | 1.3–1.5 |
| Caption | 12–14 px | 1.3–1.5 |

Treść ciągła ma kontrolowaną długość wiersza — typowo 45–75 znaków.
Hierarchii nie buduje się kolorem; podstawą są rozmiar, grubość, odstęp i
kolejność. Nagłówki i tekst ciągły mają osobne wartości interlinii.

## 8. Minimalne portfolio komponentów

Button i IconButton; Link; Input, Textarea, Select, Checkbox, Radio, Switch;
Field z Label, Hint i ErrorMessage; Alert i Toast; Dialog, Drawer, Popover;
Tabs i Accordion; Table; Card; Skeleton i Spinner; VisuallyHidden; oraz
prymitywy układu: Stack, Cluster, Grid, Container.

Każdy komponent dokumentuje: API i dozwolone warianty, używane tokeny, stany
i obsługę klawiatury, dostępną nazwę oraz relacje ARIA, przykłady poprawnego i
błędnego użycia, testy, a także historię zmian i politykę wycofywania.

Nienastylowane prymitywy z zewnętrznej biblioteki (Radix i podobne) oraz
generatory wklejające kod do repozytorium (shadcn/ui i podobne) skracają
drogę, ale **nie zwalniają z testów klawiatury, czytnika ekranu i stylów
focus**. Gotowy komponent jest punktem startu, nie certyfikatem dostępności.

## 9. Gate

- **Brak wartości surowych w komponentach** — grep na literały kolorów i
  odstępów poza warstwą tokenów. Deterministyczne, tanie, blokujące.
- **Kompletność mapowania** — każdy token semantyczny zdefiniowany w każdym
  wariancie (jasny, ciemny, wysoki kontrast). Brak = błąd builda.
- **Automatyczne testy dostępności** (axe-core i podobne) w CI — najpierw
  raportowo, potem blokująco dla błędów wykrywalnych automatycznie.
- **Testy wizualne** dla stanów komponentów.
- **Audyt jakości** (Lighthouse CI i podobne) jako sygnał regresji.

Narzędzia automatyczne wykrywają ułamek problemów dostępności. Testu
klawiaturą i czytnikiem ekranu nie zastępuje żaden skaner — to samo
rozróżnienie, co między skanerem bezpieczeństwa a przeglądem człowieka.

## 10. Lista kontrolna przed wydaniem

**Design system:** brak kolorów i odstępów zaszytych w komponentach; każdy
komponent używa tokenów semantycznych; wariant jasny, ciemny i
wysokokontrastowy mają komplet mapowań; wszystkie stany opisane i
przetestowane; dokumentacja pokazuje też błędne użycia; zmiana tokenów jest
wersjonowana.

**Dostępność:** kontrast 4.5:1 dla tekstu i 3:1 dla dużego tekstu oraz
kontrolek; informacja nie zależy wyłącznie od koloru; cała aplikacja działa z
klawiatury; focus widoczny i niezasłonięty; ikony dekoracyjne ukryte przed
technologiami asystującymi; przycisk z samą ikoną ma dostępną nazwę;
`prefers-reduced-motion` usuwa ruch nieistotny; sprawdzono tryb ciemny,
wymuszone kolory i powiększenie do 200%.

## Źródła referencyjne

- W3C: [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- W3C: [Understanding Contrast
  (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html),
  [Non-text
  Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html),
  [Focus
  Appearance](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance.html)
- MDN:
  [oklch()](https://developer.mozilla.org/en-US/docs/Web/CSS/color_value/oklch),
  [prefers-color-scheme](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-color-scheme),
  [prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion),
  [:focus-visible](https://developer.mozilla.org/en-US/docs/Web/CSS/:focus-visible)
- [Material Design 3 — warstwy
  tokenów](https://m3.material.io/foundations/design-tokens/overview)
- [USWDS — Design Tokens](https://designsystem.digital.gov/design-tokens/)
- [Carbon — Color Tokens](https://carbondesignsystem.com/elements/color/tokens/)
- [Design Tokens Format Module](https://tr.designtokens.org/format/) (raport
  grupy roboczej)
- [Style Dictionary](https://styledictionary.com/),
  [Storybook](https://storybook.js.org/),
  [axe-core](https://github.com/dequelabs/axe-core),
  [Playwright](https://playwright.dev/)

Powiązane: [`rules-as-gates.md`](rules-as-gates.md), [`ci-cd.md`](ci-cd.md),
[`third-party-assets-privacy.md`](third-party-assets-privacy.md) i
[`security-verification-gates.md`](security-verification-gates.md).
