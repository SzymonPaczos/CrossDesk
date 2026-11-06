# Instrukcje agentów — źródła i granice pomiaru

Zebrano: 2026-09-08. Przegląd: 2026-12-08.
Zebrał: autor zmiany; niezależny review sprawdził źródła Anthropic i pracę ETH.
Grounding: twierdzenia poniżej odnoszą się do wskazanych publikacji;
zastosowanie w toolkicie jest oznaczone osobno. Materiał czytany na żądanie.

## Co mówią źródła

- [Anthropic, Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents),
  2025-09-29: kontekst ma zawierać potrzebną informację na odpowiednim
  poziomie szczegółowości. Odczyt przez odsyłacze ogranicza stały kontekst,
  ale kosztuje dodatkowe wyszukiwanie. „Minimalny” nie oznacza zawsze krótki.
- [Anthropic, Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices),
  odczyt 2026-09-08: wyniki i ograniczenia powinny być jawne; kolejność ma
  znaczenie przy zadaniach, które jej wymagają. Ostrzeżenie przed agresywnymi
  dyrektywami narzędziowymi dotyczy konkretnych modeli i wymaga ponownej oceny
  przy migracji. Nie ustanawia ogólnego zakazu słów oznaczających wymagania.
- [OpenAI, Model guidance](https://developers.openai.com/api/docs/guides/latest-model),
  odczyt 2026-09-08: instrukcje należy oceniać pod kątem duplikatów i konfliktów,
  a dodatkową weryfikację dopasować do ryzyka. Wymagania projektu pozostają
  częścią zadania. Strona dotyczy wskazanej na niej rodziny modeli;
  nie dowodzi przewagi dowolnego modelu przy krótszym kontekście.
- [Gloaguen i in., Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?](https://arxiv.org/html/2602.11988v2),
  ETH Zurich i LogicStar.ai, v2 z 2026-06-23: CTXbench obejmuje 138 zadań
  z 12 repozytoriów, dodatkowo badano 300 zadań SWE-bench Lite. Względem
  braku pliku zmiany skuteczności nie były statystycznie istotne; kontekst
  wygenerowany przez LLM zwiększał koszt średnio o 20% i 23% w obu zbiorach.
  Długość pliku nie wyjaśniała wyraźnie skuteczności. Badano zadania Python,
  konkretne modele i po jednym przebiegu konfiguracji; kryterium stanowiły
  testy, nie pełna ocena bezpieczeństwa. V1 używała nazwy AGENTbench;
  skrót „skuteczność −3%” nie oddaje wniosku v2.

## Zastosowanie w toolkicie

Usuwanie duplikatów i nieuzasadnionych procedur zostawia cele, upoważnienia,
decyzje oraz potrzebną wiedzę. Krótki przykład pomaga znaleźć diagnozę,
ale nie dostarcza faktów o aktualnym projekcie: przykładowe AUD-03 nie
uprawnia do stwierdzenia, że badany panel ujawnia dane.

Pomiar poprawy instrukcji może porównać zamrożone wersje na tych samych
zadaniach, z tą samą konfiguracją modelu, narzędzi i kryteriami oceny.
Wynik rozdziela poprawność wykonania, odzyskanie potrzebnej informacji,
niepoparte twierdzenia, koszt i czas. Pytanie o treść pliku mierzy inne
zachowanie niż naprawa z testem. Powtórzenia i zamiana kolejności pozwalają
ocenić zmienność; pojedynczy przebieg nie rozstrzyga przewagi modeli.

Przypadek kontrolny może wymagać poprawnego rozpoznania zieleni po obu
stronach mutacji albo odmowy dopisania faktów do samego identyfikatora AUD-03.
Liczba słów mierzy rozmiar; tokeny wymagają wskazanego tokenizera lub
telemetrii wykonania. Brak telemetrii oznacza brak pomiaru tokenów.

Ta zmiana nie przeprowadza nowego A/B modeli. Dane kosztowe z JawnePaństwo
w `test-execution-economy.md` pozostają historycznym pomiarem konkretnej sesji.

## Metoda porównania z regułą i bez (uzupełnienie 2026-09-14)

Uzupełnił: autor wydania 2026.09.14, przy adaptacji metody z zewnętrznej
biblioteki skilli (repozytorium obra/superpowers, skill `writing-skills`,
licencja MIT); treść przepisana, nie skopiowana. Weryfikacja niezależna:
nie wykonano.

Pomiar reguły przebiega jak test regresji: najpierw przebieg bez reguły
na scenariuszu, w którym jej złamanie się opłaca; dosłowny zapis
uzasadnień modelu; reguła adresująca te uzasadnienia; przebieg z regułą;
szukanie nowych obejść. Szablon: `templates/scenariusz-presji.md`.

Pomiar ma dwie części i obie są potrzebne. Pierwsza: czy krok wymagany
przez regułę został wykonany. Druga: czy wykonanie poprawiło wynik pracy
(test, bramka, artefakt) i ile kosztowało (tury, tokeny z telemetrii,
przerwania właściciela). Wynik tylko z pierwszej części mierzy
posłuszeństwo, nie skuteczność.

Ta sama biblioteka cytuje badanie Meincke i in. (2025, N=28 000), według
którego techniki perswazji w treści polecenia podnosiły zgodność
z 33% do 72%. Źródło nie zostało tu zweryfikowane i dotyczy zgodności
w rozmowie, nie wyniku pracy agentowej; zapis służy jako hipoteza dla
drugiej części pomiaru, nie jako ustalenie. Wariant ładowania reguły
(mapa czytana na żądanie, hook wstrzykujący treść co sesję) jest osobną
zmienną i porównuje się go tą samą metodą.
