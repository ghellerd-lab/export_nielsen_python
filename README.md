# Export Nielsen Python

Conversie Python pentru jobul Talend. Configuratia, logul si fisierele generate
stau in folderul acestui script: `D:\Apps\SiriusWHOAS\export_nielsen_python`.

## Ce face

1. Citeste variabilele din `D:\Apps\SiriusWHOAS\export_nielsen_python\jobExportNielsen.properties`.
2. Construieste numele perioadei: `p_data_start-p_data_final_sapt<p_sapt>`.
3. Genereaza `ARTICOLE_<societate>_<perioada>.csv` din:
   `PKG_EXPORTURI_NIELSEN.export_articol_perioada`.
4. Determina magazinele din:
   `PKG_EXPORTURI_NIELSEN.determinare_gestiuni_perioada`.
5. Pentru fiecare magazin genereaza:
   `<societate>_<perioada>_id_mag_<id>.csv` din
   `PKG_EXPORTURI_NIELSEN.vanzari_magazine_perioada`.
6. Arhiveaza fisierele generate in `<societate>_<perioada>.zip`.

Fisierele CSV sunt generate intr-un director temporar unic, care este sters
automat atat dupa succes, cat si dupa eroare. Astfel, o reluare nu poate include
fisiere ramase de la o executie esuata. Aplicatia blocheaza si doua rulari
simultane in acelasi folder de export.

## Exportul lunii precedente

Parametrul optional `last_month` se adauga in fisierul `jobExportNielsen.properties`:

```properties
last_month=y
```

Valoarea `y` (fara diferenta intre litere mari si mici si cu spatii permise in
jurul valorii) ignora `p_sapt`, `p_data_start` si `p_data_final` si genereaza
cate un ZIP pentru fiecare saptamana care intersecteaza luna calendaristica
precedenta. Fiecare perioada este o saptamana completa, de luni pana duminica;
de aceea prima si ultima perioada pot cuprinde zile din lunile vecine.

Exemplu: la o rulare in iulie 2026 sunt exportate saptamanile `20260601-20260607`,
`20260608-20260614`, `20260615-20260621`, `20260622-20260628` si
`20260629-20260705`.

Pentru orice alta valoare (inclusiv `n`, valoare goala sau parametrul absent),
functionalitatea ramane cea curenta: se genereaza un singur ZIP folosind
`p_sapt`, `p_data_start` si `p_data_final` din configuratie sau valorile lor
implicite existente.

## Parametri operationali

```properties
# Timeout conectare Oracle, in secunde
oracle_connect_timeout=30
# Timeout maxim pentru fiecare apel Oracle, in secunde
oracle_call_timeout=1800
# Include fisierul ARTICOLE in fiecare ZIP
articole=y
```

`articole=y` este trecut explicit in toate configuratiile livrate. Orice alta
valoare dezactiveaza exportul ARTICOLE. Un export care nu produce niciun fisier
este tratat ca eroare si nu este raportat ca succes.

CSV-urile sunt scrise ca in Talend: o singura coloana `LINIE` pe rand, encoding
`ISO-8859-15`, fara header.

## Instalare

```powershell
pip install -r .\requirements.txt
```

## Rulare

### Linux (productie)

Kitul Linux nu necesita Python instalat. Din folderul dezarhivat:

```bash
chmod +x run_export_nielsen_linux.sh export_nielsen/export_nielsen
./run_export_nielsen_linux.sh
```

Runnerul nu recalculeaza si nu rescrie perioada din configuratie. Pentru
`last_month=y`, aplicatia genereaza toate ZIP-urile lunii precedente. Outputul
este salvat implicit in `output/`, iar singura semnalare operationala este
logul `logs/export_nielsen_<AAAALL>.log` plus codul de iesire al procesului.
Nu este configurata nicio alerta Windows sau Linux.

Variabile optionale:

```bash
EXPORT_NIELSEN_OUTPUT_DIR=/cale/output
EXPORT_NIELSEN_LOG_DIR=/cale/loguri
```

Pentru programarea in prima luni a lunii sunt incluse
`export-nielsen.service` si `export-nielsen.timer`. Exemplul presupune instalarea
kitului in `/opt/export_nielsen` si un cont Linux dedicat `exportnielsen`.
Administratorul creeaza in prealabil directoarele `output/` si `logs/`, le acorda
contului jobului si instaleaza unitatile:

```bash
sudo install -m 0644 export-nielsen.service /etc/systemd/system/
sudo install -m 0644 export-nielsen.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now export-nielsen.timer
systemctl list-timers export-nielsen.timer
```

Nu exista unitate `OnFailure`; rezultatul se verifica in logul local sau cu
`journalctl -u export-nielsen.service`.

### Windows / dezvoltare

```powershell
.\run_export_nielsen.ps1
```

Scriptul foloseste executabilul portabil daca acesta exista langa script; in
mediul de dezvoltare foloseste Python. Outputul este afisat pe ecran si adaugat
in `logs\export_nielsen_<AAAALL>.log`, iar codul de iesire este propagat catre
Task Scheduler.

Daca runnerul Windows este folosit si exportul intoarce un cod diferit de zero, acesta:

- scrie detaliul in `logs\export_nielsen_ALERTE.log`;
- incearca sa creeze un eveniment `ERROR`, sursa `ExportNielsen`, ID `100`, in
  jurnalul Windows `Application`;
- pastreaza acelasi cod de eroare pentru istoricul Task Scheduler.

Evenimentul poate fi monitorizat de sistemul de alertare al companiei. Crearea
evenimentului necesita ca taskul sa aiba dreptul de a scrie in Event Log;
fisierul de alerte este produs indiferent daca Event Log refuza operatia.

Sau din CMD / dublu-click:

```bat
run_export_nielsen.bat
```

Sau direct:

```powershell
& "C:\Users\Daniel.GHELLER\AppData\Local\Programs\Python\Python312\python.exe" .\export_nielsen.py
```

Scriptul foloseste `python-oracledb`. Daca Oracle Client nu este instalat,
modul thin al librariei ar trebui sa fie suficient pentru conexiunea simpla cu
host/port/SID.

## Programare lunara in productie

Inainte de instalare seteaza `last_month=y`, apoi deschide PowerShell ca
Administrator si ruleaza:

```powershell
.\install_monthly_task.ps1 -Time "03:00"
```

Taskul ruleaza in prima luni din fiecare luna, implicit sub contul `SYSTEM`.
Pentru alt cont foloseste `-RunAs "DOMENIU\cont_job"`. Daca trimiterea se face
prin Outlook local, taskul trebuie rulat sub un cont dedicat care are profil
Outlook; pentru `SYSTEM` se recomanda SMTP.

## Drepturi de acces

Nu se acorda acces grupului `Everyone`. Pentru a permite modificarea numai
contului jobului, administratorilor locali si contului `SYSTEM`, deschide
PowerShell ca Administrator si ruleaza:

```powershell
.\set_access_everyone.ps1 -JobAccount "DOMENIU\cont_job"
```

Numele scriptului este pastrat pentru compatibilitate, dar comportamentul vechi
care acorda acces tuturor a fost eliminat. Configuratia contine parola Oracle si
trebuie protejata prin aceste drepturi.

## Structura codului

- `export_nielsen.py` orchestreaza rularea si ramane punctul unic de pornire;
- `nielsen_config.py` contine configuratia si calculul perioadelor;
- `nielsen_oracle.py` contine conexiunea si exporturile Oracle/CSV;
- `nielsen_files.py` contine blocarea, logul si arhivarea;
- `nielsen_email.py` contine metodele Outlook si SMTP.

Separarea nu schimba argumentele liniei de comanda sau modul de instalare.
