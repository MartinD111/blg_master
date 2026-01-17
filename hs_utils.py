import pandas as pd
import zipfile
import io
import re
import os

class HSCodeExtractor:
    def __init__(self):
        """
        Inicilizacija ekstraktorja.
        """
        self.seen_vins = set()
        self.extracted_data = []

    def reset(self):
        """Počisti prejšnje rezultate."""
        self.seen_vins.clear()
        self.extracted_data = []

    def get_packing_name(self, filename):
        """Replicira JS: filename.match(/pack_(\d+)/i)"""
        match = re.search(r'pack_(\d+)', filename, re.IGNORECASE)
        return match.group(1) if match else "-"

    def process_excel(self, file_content, filename):
        """Obdela posamezno Excel datoteko (bytes ali path)"""
        try:
            # Preberemo brez headerja, da lahko sami iščemo vrstice (kot v JS)
            df = pd.read_excel(file_content, header=None)
            
            vin_idx = -1
            hs_idx = -1
            start_row = 0
            
            # 1. Iskanje Headerja (prvih 20 vrstic)
            # JS logika: loop r<20, išče "VIN" ali "FAHRGESTELL"
            for r in range(min(20, len(df))):
                row_values = df.iloc[r].astype(str).str.upper().tolist()
                for c, cell_value in enumerate(row_values):
                    if "VIN" in cell_value or "FAHRGESTELL" in cell_value:
                        vin_idx = c
                        hs_idx = c + 1
                        start_row = r + 1
                        break
                if vin_idx != -1:
                    break
            
            # 2. Fallback (če ne najde headerja)
            # JS logika: if(vinIdx === -1) { vinIdx = 2; hsIdx = 3; startRow = 11; }
            if vin_idx == -1:
                vin_idx = 2  # Stolpec C
                hs_idx = 3   # Stolpec D
                start_row = 11

            packing_name = self.get_packing_name(filename)

            # 3. Ekstrakcija podatkov
            for i in range(start_row, len(df)):
                # Preverimo, če vrstica in stolpec obstajata
                if i >= len(df) or vin_idx >= df.shape[1]:
                    continue

                # Handle potential float/NaN or whitespace values
                val = df.iloc[i, vin_idx]
                vin = str(val).strip() if pd.notna(val) else ""
                
                # Preverimo dolžino in duplikate (JS: vin.length > 10)
                if len(vin) > 10 and vin not in self.seen_vins:
                    hs_code = ""
                    if hs_idx < df.shape[1]:
                        hs_val = df.iloc[i, hs_idx]
                        hs_code = str(hs_val).strip() if pd.notna(hs_val) else ""

                    self.seen_vins.add(vin)
                    self.extracted_data.append({
                        "vin": vin,
                        "hs": hs_code,
                        "file": filename,
                        "packing": packing_name
                    })

        except Exception as e:
            print(f"Napaka pri datoteki {filename}: {e}")

    def process_file(self, file_content, filename):
        """Main entry point to support both ZIP and Excel similar to previous Utils logic"""
        self.reset()
        file_stream = io.BytesIO(file_content)

        if filename.lower().endswith('.zip'):
             with zipfile.ZipFile(file_stream) as z:
                for z_filename in z.namelist():
                    if not z_filename.startswith('__MACOSX') and z_filename.lower().endswith(('.xlsx', '.xls')):
                        with z.open(z_filename) as f:
                            content = f.read()
                            # Use io.BytesIO since pandas expects a file-like object
                            self.process_excel(io.BytesIO(content), z_filename)
        elif filename.lower().endswith(('.xlsx', '.xls')):
            self.process_excel(file_stream, filename)
        
        return self.extracted_data
