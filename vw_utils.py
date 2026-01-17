import pandas as pd
import zipfile
import io
import re
import os

class VWHSExtractor:
    def __init__(self):
        """
        Inicilizacija ekstraktorja.
        """
        self.seen_vins = set()
        self.results = []

    def reset(self):
        """Počisti prejšnje rezultate."""
        self.seen_vins.clear()
        self.results = []

    def process_file(self, file_obj, filename):
        """
        Glavna funkcija za obdelavo. Sprejme datoteko (bytes ali path) in ime.
        Samodejno zazna ali gre za ZIP ali Excel.
        """
        self.reset() # Reset before processing new file
        
        # Če je input bytes (kot je običajno pri web uploadu)
        if isinstance(file_obj, bytes):
            file_stream = io.BytesIO(file_obj)
        else:
            # Če je file path
            with open(file_obj, 'rb') as f:
                file_stream = io.BytesIO(f.read())

        if filename.lower().endswith('.zip'):
            self._process_zip(file_stream)
        elif filename.lower().endswith(('.xlsx', '.xls')):
            self._process_excel(file_stream, filename)
        
        return self.results

    def _process_zip(self, zip_stream):
        """Rekurzivno odpre ZIP in poišče Excel datoteke."""
        with zipfile.ZipFile(zip_stream) as z:
            for zip_filename in z.namelist():
                # Ignoriraj mape in MACOSX sistemske datoteke
                if not zip_filename.endswith('/') and '__MACOSX' not in zip_filename:
                    if zip_filename.lower().endswith(('.xlsx', '.xls')):
                        with z.open(zip_filename) as excel_file:
                            # Preberemo v bytes
                            content = excel_file.read()
                            self._process_excel(io.BytesIO(content), zip_filename)

    def _process_excel(self, excel_stream, filename):
        """Logika za branje Excela in iskanje VIN/HS stolpcev."""
        try:
            # Preberemo brez headerja, da lahko sami poiščemo vrstico
            df = pd.read_excel(excel_stream, header=None)
            
            # 1. Iskanje naslovne vrstice (Header Search)
            vin_col_idx = -1
            hs_col_idx = -1
            start_row_idx = 0
            
            # Pregledamo prvih 20 vrstic
            rows_to_check = min(len(df), 20)
            
            found_header = False
            for r in range(rows_to_check):
                row_values = df.iloc[r].astype(str).str.upper().tolist()
                for c, val in enumerate(row_values):
                    if "VIN" in val or "FAHRGESTELL" in val:
                        vin_col_idx = c
                        hs_col_idx = c + 1 # Predpostavka iz JS: HS je takoj desno
                        start_row_idx = r + 1 # Podatki se začnejo eno vrstico nižje
                        found_header = True
                        break
                if found_header:
                    break
            
            # Fallback (če ne najde headerja, uporabi privzeto iz JS: Row 11, Col C=2)
            if not found_header:
                vin_col_idx = 2
                hs_col_idx = 3
                start_row_idx = 11

            # 2. Ekstrakcija Packing imena iz imena datoteke (Regex)
            # Išče vzorec "pack_123" -> vrne "123", sicer "-"
            pack_match = re.search(r"pack_(\d+)", filename, re.IGNORECASE)
            packing_name = pack_match.group(1) if pack_match else "-"

            # 3. Iteracija čez podatke
            for i in range(start_row_idx, len(df)):
                row = df.iloc[i]
                
                # Preverimo, če stolpec obstaja
                if vin_col_idx >= len(row):
                    continue

                vin = str(row[vin_col_idx]).strip()
                
                # Validacija (JS logika: > 10 znakov in unikatnost)
                if len(vin) > 10 and vin not in self.seen_vins:
                    hs_code = ""
                    if hs_col_idx < len(row):
                        hs_val = row[hs_col_idx]
                        hs_code = str(hs_val).strip() if pd.notna(hs_val) else ""

                    self.seen_vins.add(vin)
                    
                    self.results.append({
                        "vin": vin,
                        "hs_code": hs_code,
                        "packing": packing_name,
                        "source_file": filename
                    })

        except Exception as e:
            print(f"Napaka pri obdelavi datoteke {filename}: {e}")
