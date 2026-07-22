# Prompt: przygotowanie maszyny na odbiór materiałów z MacBooka

Gałąź robocza, do usunięcia po zakończeniu transferu.

Film `pararelInstaltionProcessVideo.mov` (702 MB) nigdy nie był w repozytorium
— `.gitignore` linia 78 wyklucza `*.mov`. Dlatego wymaga osobnego przesłania,
zanim projekt zniknie z MacBooka.

---

## Wklej poniższe agentowi na tej maszynie

```text
Zadanie: przygotować tę maszynę na przyjęcie pliku z MacBooka przez SSH
w sieci lokalnej, a po odbiorze zweryfikować integralność.

KROK 1 — zainstaluj klucz publiczny MacBooka
Dopisz do ~/.ssh/authorized_keys (utwórz katalog i plik, jeśli brak;
uprawnienia 700 na katalogu, 600 na pliku):

ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIM1SV53jPvxCidapq4GjOi+QgPY29AYwP0wjd6L/Rck0 mac-to-linux-20260722

KROK 2 — zgłoś dane potrzebne do połączenia
Wypisz i podaj mi z powrotem:
  whoami
  hostname
  hostname -I
  echo $HOME

KROK 3 — przygotuj miejsce
  mkdir -p ~/CrossDesk-materialy
  df -h ~          # potrzeba min. 1 GB wolnego

KROK 4 — po pojawieniu się pliku zweryfikuj
  sha256sum ~/CrossDesk-materialy/pararelInstaltionProcessVideo.mov
  stat -c %s ~/CrossDesk-materialy/pararelInstaltionProcessVideo.mov
Podaj oba wyniki. Sumę porówna właściciel z wartością po stronie Maka —
oczekiwany rozmiar to ok. 736 mln bajtów. Jeśli cokolwiek się nie zgadza,
zgłoś to i NIE potwierdzaj odbioru.

OGRANICZENIA
- Nie otwieraj żadnych portów poza już działającym SSH.
- Nie zmieniaj konfiguracji sshd poza dopisaniem klucza.
- Cofnięcie dostępu w dowolnym momencie:
  sed -i '/mac-to-linux-20260722/d' ~/.ssh/authorized_keys
```

---

## Odtworzenie projektu na Linuksie

```bash
git clone https://github.com/SzymonPaczos/CrossDesk.git
```

Repozytorium jest w całości wypchnięte — gałąź `main` bez rozbieżności.
