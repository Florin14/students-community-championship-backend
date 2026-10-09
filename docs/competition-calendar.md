# Calendarul competițional

Calendarul orientativ din imaginea organizatorului este disponibil ca șablon
editabil pentru 2026–2027 în Administrare → Sezoane → Adaugă/Editează sezon.
Apasă „Încarcă șablonul 2026–2027”, ajustează intervalele și salvează sezonul.
Încărcarea șablonului modifică doar formularul până la salvare.

Șablonul păstrează cele 24 de intervale și denumirile din imagine, inclusiv
denumirile repetate ale sferturilor și semifinalelor. Datele sunt aproximative;
nu presupunem un alt format pentru fazele eliminatorii.

| Etapă | Date |
| --- | --- |
| 1 | 26–27.10.2026 |
| 2 | 02–03.11.2026 |
| 3 | 09–10.11.2026 |
| 4 | 16–17.11.2026 |
| 5 | 23–24.11.2026 |
| Pauză | 30.11–01.12.2026 |
| 6 | 07–08.12.2026 |
| 7 | 14–15.12.2026 |
| Vacanță | 21.12.2026–10.01.2027 |
| 8 | 11–12.01.2027 |

Urmează sesiunea și pauza dintre semestre până la 21.02.2027, săptămâna
restanțelor 22–28.02, fazele eliminatorii din martie–aprilie și finala la
15.05.2027, conform intervalelor șablonului.

La programarea unui meci, calendarul sezonului are prioritate față de calculul
săptămânal. Datele de început și sfârșit sunt incluse în fiecare interval.
Pauzele, datele fără interval și fazele fără număr de etapă lasă câmpul etapei gol.
O etapă introdusă manual este păstrată când data se schimbă; butonul de
recalculare reia alegerea din calendar. Acest lucru permite reprogramări.

Calendarul este afișat în pagina publică Meciuri. Fazele fără etapă numerică
apar pe meciuri cu denumirea intervalului (`calendarLabel`). Schimbările de
calendar nu rescriu etapele, scorurile sau evenimentele meciurilor existente.

API-ul sezonului acceptă `calendar: [{startDate, endDate, label, phase, round,
isBreak}]`. Fazele sunt LEAGUE, ACADEMIC_BREAK, PLAY_OFF, FINAL_STAGES, SEMIFINALS
și FINAL. Maximum 128 de intervale, denumiri de maximum 160 de caractere, etape
întregi între 1 și 999 sau null. Intervalele se sortează cronologic la salvare și
nu se pot suprapune. Pauzele trebuie să aibă `round: null`.

Actualizările care omit calendarul îl păstrează; `calendar: []` îl golește.
Sezoanele fără calendar continuă să folosească regula săptămânală existentă.
Scrierea rămâne rezervată administratorilor, iar citirea este publică.
