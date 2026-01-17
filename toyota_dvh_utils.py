import pandas as pd
import re
import os
from datetime import datetime
import io

class ToyotaVesselDVHHelper:
    def __init__(self):
        pass

    def fuzzy_get(self, row, keywords):
        """Poišče vrednost v vrstici, če ime stolpca vsebuje eno od ključnih besed (case-insensitive)."""
        # Row keys normalization
        row_keys = {k.upper(): k for k in row.index}
        
        for kw in keywords:
            # Poišči ključ, ki vsebuje kw
            found_key = next((k for k in row_keys if kw.upper() in k), None)
            if found_key:
                return row[row_keys[found_key]]
        return None

    def map_row(self, row, vessel_name, dest_override=None):
        """Pretvori surovo vrstico v standardiziran format."""
        # 1. VIN
        vin = self.fuzzy_get(row, ['PVVIN', 'VIN']) or ''
        if not str(vin).strip(): return None # Skip prazne

        # 2. MODEL
        model = self.fuzzy_get(row, ['PVMODN', 'MODEL']) or ''

        # 3. WEIGHT
        try:
            w_val = self.fuzzy_get(row, ['PVWGHT', 'WEIGHT'])
            weight = float(str(w_val).replace(',', '.')) if w_val else 0
        except:
            weight = 0

        # 4. TARIFF (Samo za UA)
        tariff = self.fuzzy_get(row, ['PVTRCD', 'TARIFF']) or ''
        # Format tariff (če je dolg niz, dodaj presledek po 4. znaku kot v JS)
        tariff = str(tariff).strip()
        if len(tariff) >= 6 and ' ' not in tariff:
            tariff = f"{tariff[:4]} {tariff[4:6]}"

        # 5. DESTINATION logic
        if dest_override:
            dest = dest_override
        else:
            raw_dest = str(self.fuzzy_get(row, ['DESTINATION']) or '').strip().upper()
            if raw_dest == 'MZ': dest = 'PLWAW'
            elif raw_dest == 'KL': dest = 'CZPRG'
            else: dest = raw_dest

        return {
            "VIN": vin,
            "VESSEL": vessel_name,
            "DESTINATION": dest,
            "VCP": "",
            "MODEL": model,
            "WEIGHT": weight,
            "MOT": "",
            "LF": "",
            "DATE": "",
            "MRN": "",
            "DIZ": "",
            "VALUE": "",
            "TARIFF": tariff,
            "DAMAGE": ""
        }

    def process_manifest(self, master_path_or_obj, vessel_name, eta="", ua_path_or_obj=None):
        """Glavna funkcija za obdelavo Excel datotek."""
        
        # Branje Master File (vsi listi)
        try:
            xls_m = pd.ExcelFile(master_path_or_obj)
        except Exception as e:
            return {"error": f"Napaka pri branju Master datoteke: {e}"}

        rPL = []
        rCZ = [] # Vsebuje CZPRG + ATVIE
        rUA = []

        # --- SHEET 0: ATVIE ---
        if len(xls_m.sheet_names) > 0:
            df0 = pd.read_excel(xls_m, sheet_name=0)
            for _, row in df0.iterrows():
                m = self.map_row(row, vessel_name, dest_override='ATVIE')
                if m: rCZ.append(m) # AT gre v CZ skupino

        # --- SHEET 1: PL / CZ ---
        if len(xls_m.sheet_names) > 1:
            df1 = pd.read_excel(xls_m, sheet_name=1)
            for _, row in df1.iterrows():
                m = self.map_row(row, vessel_name) # Auto detect MZ/KL
                if m:
                    if m['DESTINATION'] == 'PLWAW': rPL.append(m)
                    elif m['DESTINATION'] == 'CZPRG': rCZ.append(m)
                    # Ostalo ignoriramo ali dodamo po potrebi

        # --- SHEET 2: UA ---
        if len(xls_m.sheet_names) > 2:
            df2 = pd.read_excel(xls_m, sheet_name=2)
            for _, row in df2.iterrows():
                m = self.map_row(row, vessel_name, dest_override='UAIEV')
                if m: rUA.append(m)

        # --- UA FILE (Optional) ---
        if ua_path_or_obj:
            try:
                df_u = pd.read_excel(ua_path_or_obj)
                for _, row in df_u.iterrows():
                    m = self.map_row(row, vessel_name, dest_override='UAIEV')
                    if m: rUA.append(m)
            except Exception as e:
                print(f"Napaka pri UA datoteki: {e}")

        # Dodajanje zaporednih številk (NO.)
        def add_no(arr):
            for i, item in enumerate(arr):
                item['NO.'] = i + 1
            return arr

        return {
            "PL": add_no(rPL),
            "CZ": add_no(rCZ),
            "UA": add_no(rUA),
            "meta": {"vessel": vessel_name, "eta": eta}
        }

    def export_excel_bytes(self, rows, key):
        """Izvozi Excel v bytes buffer"""
        if not rows: return None

        configs = {
            "PL": {"cols": ["NO.", "VIN", "VESSEL", "DESTINATION", "VCP", "MODEL", "WEIGHT", "MOT", "LF", "DATE", "MRN", "DIZ", "DAMAGE"]},
            "CZ": {"cols": ["NO.", "VIN", "VESSEL", "DESTINATION", "VCP", "MODEL", "WEIGHT", "MOT", "LF", "DATE", "MRN", "DIZ", "DAMAGE"]},
            "UA": {"cols": ["NO.", "VIN", "VESSEL", "DESTINATION", "VCP", "MODEL", "WEIGHT", "MOT", "LF", "DATE", "MRN", "DIZ", "VALUE", "TARIFF", "DAMAGE"]}
        }
        
        cfg = configs.get(key)
        if not cfg: return None

        output = io.BytesIO()
        df = pd.DataFrame(rows)
        
        for c in cfg["cols"]:
            if c not in df.columns: df[c] = ""
            
        df = df[cfg["cols"]]

        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        
        wb = writer.book
        ws = writer.sheets['Sheet1']

        header_fmt = wb.add_format({
            'bold': True, 'font_name': 'Calibri', 'font_size': 11,
            'bg_color': '#FFFF00', 'align': 'center', 'valign': 'vcenter', 'border': 0
        })
        cell_fmt = wb.add_format({
            'font_name': 'Calibri', 'font_size': 11,
            'align': 'center', 'valign': 'vcenter', 'text_wrap': False
        })

        for col_num, value in enumerate(df.columns.values):
            ws.write(0, col_num, value, header_fmt)
            max_len = max(df[value].astype(str).map(len).max(), len(str(value))) + 2
            ws.set_column(col_num, col_num, max_len, cell_fmt)

        writer.close()
        output.seek(0)
        return output

    def process_diz_txt(self, txt_content):
        """DIZ Obdelava (Tab 2 logika)."""
        lines = txt_content.splitlines()
        groups = {
            'PLWAW': {'lines': [], 'weight': 0},
            'CZPRG': {'lines': [], 'weight': 0},
            'UAIEV': {'lines': [], 'weight': 0}
        }
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            key = None
            if 'PLWAW' in line or 'PLAWA' in line: key = 'PLWAW'
            elif 'ATVIE' in line or 'CZPRG' in line: key = 'CZPRG'
            elif 'UAIEV' in line: key = 'UAIEV'
            
            if key:
                groups[key]['lines'].append(line)
                match = re.search(r'(\d{5})CB', line)
                if match:
                    groups[key]['weight'] += int(match.group(1))

        results = []
        for k, v in groups.items():
            if v['lines']:
                filename = f"{k}_{len(v['lines'])}x.txt"
                results.append({
                    "group": k,
                    "count": len(v['lines']),
                    "total_weight": v['weight'],
                    "filename": filename,
                    "content": "\n".join(v['lines'])
                })
        return results
