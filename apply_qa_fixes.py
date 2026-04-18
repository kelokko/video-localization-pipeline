#!/usr/bin/env python3
"""Apply QA fixes to the Google Sheet."""

import os
import gspread
from google.oauth2.service_account import Credentials
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project root (where this script lives)
PROJECT_ROOT = Path(__file__).parent.resolve()

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT = PROJECT_ROOT / 'service-account.json'
SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID', '')

# Validate config
if not SPREADSHEET_ID:
    print("ERROR: GOOGLE_SPREADSHEET_ID not set in .env")
    exit(1)
if not SERVICE_ACCOUNT.exists():
    print(f"ERROR: service-account.json not found")
    print("See setup_service_account.md for instructions")
    exit(1)

# QA fixes from review - row number, QA status, improved Finnish
FIXES = [
    (5, "TYPO", "Opastan sinut Medikro spirometriajärjestelmän perusteisiin: järjestelmän käyttöönotosta tarkkaan kalibrointiin, kalibroinnin tarkistukseen, tutkimuksen suorittamiseen ja tulosten tulkintaan."),
    (6, "OVER→FIXED", "Yhdessä opimme tarkan hengitystutkimuksen tekemisen taidot."),
    (15, "AWKWARD→FIXED", "Bakteerifiltteri ja Grip auttavat tässä."),
    (46, "OVER→FIXED", "Aloita kalibrointitarkistus klikkaamalla painiketta."),
    (55, "AWKWARD→FIXED", "Tarkista vuotojen varalta."),
    (118, "ERROR→FIXED", "Sinä olet..."),
    (149, "OVER→FIXED", "Älä laita jalkoja ristiin."),
    (159, "WRONG_TERM→FIXED", "koska se voi aiheuttaa ääniraon sulkeutumisen, mikä estää kaiken ilman ulospääsyn."),
    (174, "OVER→FIXED", "Nenäpuristin laitetaan näin."),
    (177, "OVER→FIXED", "Grip helpottaa pitämistä."),
    (179, "WRONG_TERM→FIXED", "se voi tukkia hengitystiet ja aiheuttaa ääniraon sulkeutumisen."),
    (193, "OVER→FIXED", "Potilas hengittää normaalisti ja rentoutuu, näin mittaus aloitetaan."),
    (197, "OVER→FIXED", "Aloita mittaus."),
    (198, "OVER+REP→FIXED", "Laita nenäpuristin, aseta virtausanturi suuhun, hengitä normaalisti."),
    (203, "OVER→FIXED", "Aseta virtausanturi potilaan suuhun ja hengitä normaalisti."),
    (232, "OVER→FIXED", "Kaikki normaalirajoissa."),
    (253, "OVER→FIXED", "Mutta teen uudelleen."),
    (257, "OVER→FIXED", "Eli noin 2 %."),
    (264, "NONSENSE→FIXED", "Voin tarkastella virtauksia hengityksessä."),
    (271, "OVER→FIXED", "Katsotaan kaikki numeeriset arvot."),
    (272, "OVER→FIXED", "Ensimmäinen ei ollut paras, vaan viimeinen."),
    (291, "OVER→FIXED", "Katsotaan numeeriset arvot."),
    (299, "OVER→FIXED", "Yhdellä silmäyksellä näet, ovatko tulokset normaalit."),
    (306, "OVER→FIXED", "Tässä osiossa on samat numeeriset tiedot, jotka näytin aiemmin."),
    (318, "OVER→FIXED", "Ja tulostustoiminto."),
    (321, "OVER→FIXED", "On kaksi vaihtoehtoa."),
    (356, "WRONG_TERM→FIXED", "sisältävät joko ääniraon sulkeutumisen tai muun varhaisen keskeytyksen."),
]

def main():
    print("Connecting to Google Sheets...")
    creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT), scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
    
    # Get headers
    headers = sheet.row_values(1)
    
    # Find column indices (1-indexed for gspread)
    finnish_col = headers.index('Finnish') + 1
    qa_col = headers.index('QA Status') + 1
    improved_col = headers.index('Improved Finnish') + 1
    
    print(f"Applying {len(FIXES)} fixes...")
    
    for row_num, status, improved_text in FIXES:
        print(f"  Row {row_num}: {status}")
        # Update QA Status
        sheet.update_cell(row_num, qa_col, status)
        # Update Improved Finnish column
        sheet.update_cell(row_num, improved_col, improved_text)
        # Also update the main Finnish column with the fix
        sheet.update_cell(row_num, finnish_col, improved_text)
    
    # Mark all other rows as OK
    print("\nMarking remaining rows as OK...")
    all_qa = sheet.col_values(qa_col)
    for i in range(2, len(all_qa) + 100):  # Go a bit beyond to catch all
        if i <= len(all_qa) and all_qa[i-1]:
            continue  # Already has status
        try:
            # Check if row has data
            finnish = sheet.cell(i, finnish_col).value
            if finnish:
                sheet.update_cell(i, qa_col, "OK")
        except:
            break
    
    print(f"\nDone! {len(FIXES)} fixes applied.")
    print(f"View at: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")

if __name__ == '__main__':
    main()
