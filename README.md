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
