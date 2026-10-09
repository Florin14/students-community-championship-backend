# Prezențe și operatori

Prima versiune distribuie un QR individual la începutul turneului. Jucătorul
îl poate prezenta pe telefon sau pe un ecuson tipărit, fără cont obligatoriu.
Un cont personal poate fi adăugat ulterior pentru a afișa același credential.
QR-ul conține un identificator semnat, fără nume, fotografie sau token de login.

Administratorul încarcă o fotografie clară, înscrie echipa în sezon și emite
codul din administrarea jucătorilor. Codul este specific sezonului și echipei;
regenerarea, revocarea și transferul la altă echipă invalidează codurile vechi.
Înainte de un transfer ori de schimbarea echipelor unui meci, administratorul
trebuie să corecteze prezențele deja confirmate pentru acel meci neînceput.
Fotografia este obligatorie la crearea și salvarea unui jucător, la emiterea
QR-ului și la scanare. Adminul încarcă fotografia; aceasta nu poate fi ștearsă
prin actualizarea profilului. Jucătorii existenți fără poză sunt păstrați, dar
au nevoie de o fotografie pentru a putea fi salvați sau verificați.
QR-ul identifică profilul;
operatorul trebuie să compare persoana cu fotografia înainte de confirmare.

`OPERATOR` este singurul rol pentru personalul de la stadion. Operatorii pot citi profiluri, loturi și
statistici de prezență și pot
confirma o prezență. Pot folosi consola live pentru toate meciurile deschise:
porni/pauza/relua/finaliza meciul, adăuga goluri cu marcatori și pase decisive,
cartonașe, corecta evenimente și introduce audiența. Nu pot edita jucători,
echipe, sezoane sau conturi, emite QR-uri ori anula prezențe. Administratorii pot
folosi și ei fluxul de prezență. Un cont dezactivat pierde imediat accesul.

Prezența este unică per jucător și meci, confirmată înainte de prima pornire
a meciului. Repetarea cererii nu dublează prezența. O reluare/reopen a meciului
nu redeschide înscrierile. Administratorii pot corecta prezențe înainte de
start, cu motiv obligatoriu; auditul păstrează autorul și istoricul. Statisticile
numără sosirile confirmate, nu minutele jucate. Anulările sunt excluse.

## API

Pentru o bază locală nouă, copiază `.env.template` în `.env`, alege propria
valoare `DEFAULT_ADMIN_PASSWORD` și rulează `docker compose up -d --build`.
Migrarea creează primul super-admin doar dacă nu există deja un administrator;
emailul implicit este `admin@scc.ro`. Apoi creează conturile cu rol Operator
din Administrare → Conturi și emite QR-urile din Administrare → Jucători.

- `POST /users/` cu `role: "OPERATOR"`: cont de operator (admin).
- `GET /matches/mine`: toate meciurile deschise pentru operatori
  și administratori; asignările indică responsabilul, fără să limiteze accesul.
- `GET /matches/` și `GET /matches/{id}`: includ numărul de jucători verificați
  la acel meci (`attendanceHome`, `attendanceAway`, `attendanceTotal`).
  Detaliile individuale rămân în API-ul autentificat de prezențe.
- `GET /stats/audience?seasonId=&skip=&limit=`: total spectatori, media și maximul
  per meci, număr de meciuri cu audiența completată și clasamentul meciurilor.
  Numără doar meciuri finalizate; include valoarea 0 și exclude null. Totalurile
  nu sunt afectate de paginarea clasamentului.
- `PUT /matches/{id}/audience` cu `{audience: 125}`: număr de spectatori;
  valoarea poate fi 0 sau null (necunoscut), niciodată negativă ori fracționară.
  Modificările din live sunt auditate și se pot face înainte de confirmarea
  rezultatului. Adminul poate completa audiența și în formularul meciului.
- `POST /players/{id}/qr` cu `{seasonId, regenerate?}`: emitere/afișare QR
  (admin). Răspunsul conține `token`; interfața generează un QR descărcabil SVG.
- `POST /players/{id}/qr/revoke` cu `{seasonId}`: revocare (admin).
- `GET /attendance/matches/{id}`: loturi, prezențe și posibilitatea confirmării.
- `POST /attendance/matches/{id}/scan` cu `{token}`: verifică codul și
  returnează fotografia/profilul, fără să înregistreze o prezență.
- `POST /attendance/matches/{id}/confirm` cu `{token, identityConfirmed: true}`:
  confirmă prezența după verificarea vizuală.
- `POST /attendance/{id}/void` cu `{reason}`: corectare (admin).
- `GET /stats/attendance?seasonId=&teamId=&playerId=&skip=&limit=`: statistici
  detaliate, inclusiv jucători cu zero prezențe (autentificare necesară).
- `GET /stats/overview`: include `attendances`, `attendancePlayers` și
  `attendanceMatches`. Profilul public include `attendanceCount` pentru sezon.

Scanarea din cameră necesită permisiunea utilizatorului și HTTPS (sau localhost).
Interfața permite și citirea unui QR dintr-o imagine ori introducerea codului.
După modificări se reconstruiește imaginea și se aplică migrările prin
`docker compose up -d --build`. Baza de date și volumele existente se păstrează.

Migrarea `d6a9218f4c73` convertește conturile vechi `VOLUNTEER` la `OPERATOR`,
păstrând ID-ul, parola, starea activă/dezactivată, asignările și istoricul de
prezențe/audit. Rolul vechi nu mai este acceptat la crearea sau editarea conturilor.
Sesiunile existente rămân valide: serverul citește rolul curent din baza de date,
iar interfața actualizează rolul salvat local. Revenirea la migrarea anterioară
permite din nou valoarea veche, fără să schimbe sau să dezactiveze operatorii.
