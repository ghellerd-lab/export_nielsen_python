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

CSV-urile sunt scrise ca in Talend: o singura coloana `LINIE` pe rand, encoding
`ISO-8859-15`, fara header.

## Instalare

```powershell
pip install -r .\requirements.txt
```

## Rulare

```powershell
.\run_export_nielsen.ps1
```

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

## Acces pentru toti utilizatorii

Pentru ca folderul exportului si fisierele generate ulterior sa fie accesibile
tuturor utilizatorilor Windows, ruleaza:

```powershell
.\set_access_everyone.ps1
```
