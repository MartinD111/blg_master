import pandas as pd
import io
import re
from datetime import datetime

class ToyotaTrainProcessor:
    def __init__(self):
        # Slovar možnih imen stolpcev (kot v JS)
        self.col_map = {
            'vin': ['VIN', 'VEHICLEUSEVIN', 'SASIJA'],
            'mot': ['MOT', 'VAGON', 'OZNAKA_PS', 'VEHICLEUSELOADINGMEANSOFTRANSPORTNUMBER', 'ACTUALMEANSOFTRANSPORT'],
            'weight': ['WEIGHT', 'TEZA', 'NETO', 'WGT', 'MASS'],
            'dest': ['DESTINATION', 'DEST', 'VEHICLEUSEDESTINATIONCODE', 'CILJ'],
            'model': ['MODEL', 'VEHICLEUSEMODELCODE'],
            'mrn': ['MRN', 'MRN_TEZA'],
            'vessel': ['VESSEL', 'LADJA'],
            'value': ['VALUE', 'VREDNOST', 'AMOUNT', 'PRICE'],
            'damage': ['DAMAGE', 'POSKODBE', 'REMARK']
        }

    def normalize_headers(self, df):
        """Poišče pravo vrstico z naslovi (header), če ni v prvi vrstici."""
        # Če je VIN že v stolpcih, super
        if any(c for c in df.columns if str(c).upper() in self.col_map['vin']):
            return df

        # Išči v prvih 10 vrsticah
        for i in range(min(10, len(df))):
            row = df.iloc[i].astype(str).str.upper().tolist()
            if any(x in row for x in self.col_map['vin']):
                # Nastavi to vrstico kot header
                df.columns = df.iloc[i]
                return df.iloc[i+1:].reset_index(drop=True)
        return df

    def find_col(self, df, key):
        """Poišče ime stolpca glede na alias seznam."""
        cols = [str(c).upper().strip() for c in df.columns]
        for alias in self.col_map.get(key, []):
            for col in cols:
                if alias in col:
                    return df.columns[cols.index(col)]
        return None

    def process_phase_1(self, odstrel_bytes, plan_bytes, is_t1=False):
        """
        FAZA 1: Združi Odstrelek (Luka Koper) in Plan.
        """
        # 1. Branje datotek
        df_odstrel = pd.read_excel(io.BytesIO(odstrel_bytes))
        df_plan = pd.read_excel(io.BytesIO(plan_bytes))

        # 2. Normalizacija headerjev
        df_odstrel = self.normalize_headers(df_odstrel)
        df_plan = self.normalize_headers(df_plan)

        # 3. Identifikacija ključnih stolpcev
        vin_col_o = self.find_col(df_odstrel, 'vin')
        vin_col_p = self.find_col(df_plan, 'vin')

        if not vin_col_o or not vin_col_p:
            raise ValueError("Stolpec VIN ni najden v eni od datotek.")

        # Priprava Plan slovarja za hitro iskanje (VIN -> Row Data)
        # Zaradi duplikatov odstranimo presledke
        df_plan[vin_col_p] = df_plan[vin_col_p].astype(str).str.strip()
        df_odstrel[vin_col_o] = df_odstrel[vin_col_o].astype(str).str.strip()

        # Left Join (Odstrel je master)
        merged = pd.merge(df_odstrel, df_plan, left_on=vin_col_o, right_on=vin_col_p, how='left', suffixes=('_O', '_P'))

        # 4. Konstrukcija končne tabele (WAG format)
        final_data = []
        
        # Poišči stolpce v obeh tabelah (prioriteta PLAN, potem ODSTREL)
        def get_val(row, key):
            # Poskusi najti v Planu (P), če ne, v Odstrelu (O)
            col_p = self.find_col(df_plan, key)
            if col_p and pd.notna(row.get(col_p)): return row[col_p]
            
            col_o = self.find_col(df_odstrel, key)
            if col_o and pd.notna(row.get(col_o)): return row[col_o]
            return ""

        seq = 1
        for idx, row in merged.iterrows():
            vin = row[vin_col_o]
            if len(str(vin)) < 5: continue # Skip prazne/smeti

            wagon = get_val(row, 'mot')
            weight = get_val(row, 'weight')
            
            # LF Logika (kot v JS)
            lf = ""
            if "429" in str(wagon): lf = "10"
            elif "437" in str(wagon): lf = "13"

            entry = {
                'NO.': seq,
                'VIN': vin,
                'VESSEL': get_val(row, 'vessel'),
                'DESTINATION': get_val(row, 'dest'),
                'MODEL': get_val(row, 'model'),
                'WEIGHT': weight,
                'MOT': wagon,
                'LF': lf,
                'MRN': get_val(row, 'mrn'),
                # Datum logika
                'DATE': datetime.now().strftime("%d.%m.%Y") # Poenostavljeno, v praksi parsaš stolpec DATE
            }

            # Dodajanje T1 vrednosti
            if is_t1:
                entry['VALUE'] = get_val(row, 'value')
                # Pretvori v float za seštevanje
                try: entry['VALUE'] = float(str(entry['VALUE']).replace(',', '.')) 
                except: entry['VALUE'] = 0

            # Dodajanje poškodb (iz Plana)
            # Tu bi morali iterirati skozi vse stolpce 'DAMAGE' v planu
            # Za demo poenostavljeno:
            entry['DAMAGE'] = "" 
            
            final_data.append(entry)
            seq += 1

        return pd.DataFrame(final_data)

    def process_phase_2(self, df_wag):
        """
        FAZA 2: Generiranje statistike (eTL tabela, Report tekst, itd.)
        """
        # Zagotovi numerične teže
        df_wag['WEIGHT'] = pd.to_numeric(df_wag['WEIGHT'], errors='coerce').fillna(0)
        
        # Statistika po vagonih
        wagons = df_wag.groupby('MOT').agg({
            'WEIGHT': 'sum',
            'LF': 'first', # Vzame prvo vrednost
            'VIN': 'count'
        }).reset_index()

        # Skupne vsote
        total_weight = df_wag['WEIGHT'].sum()
        total_cars = len(df_wag)
        total_value = df_wag['VALUE'].sum() if 'VALUE' in df_wag.columns else 0

        # Priprava report teksta
        report_text = f"{len(wagons)} Wagen mit Toyota Fahrzeuge\n"
        report_text += f"Skupaj/zusammen - {total_cars} vozil, teza {total_weight} kg"

        return {
            "wagons": wagons.to_dict(orient='records'),
            "stats": {
                "total_weight": total_weight,
                "total_cars": total_cars,
                "total_value": total_value,
                "wagons_count": len(wagons)
            },
            "report_text": report_text
        }
