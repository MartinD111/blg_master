import pandas as pd
import re
import os
import io
from datetime import datetime

class VWAttListaHelper:
    def __init__(self):
        # Destinacije (kopirano iz JS)
        self.destinations_map = {
            "EGYAG": "ALEXANDRIA (EGIPT)", "AZEMQ": "AZERBAIJAN", "CYPEY": "LIMASSOL (CIPER)",
            "GEODB": "GEORGIA", "CYPXP": "LIMASSOL (CIPER)", "CYPEZ": "NORTH CYPRUS",
            "GRCGR": "PIRAEUS (GRČIJA)", "GRCDP": "PIRAEUS (GRČIJA)", "ILASH": "HAIFA",
            "ILHFA": "HAIFA", "ILPAL": "PALESTINA (HAIFA)", "LBNLJ": "BEIRUT",
            "MTSGW": "LA VALLETTA (MALTA)", "TNTUN": "LA GOULLETE (TUNISIJA)", 
            "TREYP": "EFESAN (TURČIJA)", "LIMA": "LIMASSOL (CIPER)", "PIRE": "PIRAEUS (GRČIJA)"
        }

    def clean_destination(self, name):
        """Odstrani oklepaje in odvečne presledke (npr. 'ALEXANDRIA (EGIPT)' -> 'ALEXANDRIA')"""
        if not name: return ""
        return re.sub(r'\s*\(.*?\)\s*', '', str(name)).strip()

    def clean_hs_code(self, code):
        """Očisti HS kodo in jo skrajša na 6 znakov, če je potrebno"""
        if not code: return "UNKNOWN"
        code = str(code).strip()
        clean = re.sub(r'[^a-zA-Z0-9]', '', code)
        if len(clean) >= 6 and clean.isdigit():
            return clean[:6]
        return clean

    def load_and_process(self, csv_file_obj, chassis_list, diz_list, swb_no):
        """
        Glavna funkcija za obdelavo podatkov.
        Inputs:
            csv_file_obj: file object or path to VW Stock CSV datoteke
            chassis_list: seznam nizov (VIN številke)
            diz_list: seznam nizov (DIZ številke)
            swb_no: SWB številka
        """
        # 1. Branje CSV datoteke
        try:
            # VW CSV običajno uporablja podpičje
            df = pd.read_csv(csv_file_obj, sep=';', on_bad_lines='skip', dtype=str)
        except:
            # Fallback na vejico (try re-reading if stream allows seek)
            if hasattr(csv_file_obj, 'seek'):
                csv_file_obj.seek(0)
            df = pd.read_csv(csv_file_obj, sep=',', on_bad_lines='skip', dtype=str)

        # Normalizacija imen stolpcev (v velike črke in brez presledkov)
        df.columns = [c.strip().upper() for c in df.columns]

        # Iskanje ključnih stolpcev (dinamično, kot v JS)
        col_map = {}
        for c in df.columns:
            if "CHASSIS" in c: col_map['CHASSIS'] = c
            elif "DESTINATION" in c: col_map['DESTINATION'] = c
            elif "INVOICE" in c: col_map['INVOICE'] = c
            elif "DESCRIPTION" in c and "DAMAGE" not in c: col_map['DESCRIPTION'] = c
            elif "WEIGHT" in c: col_map['WEIGHT'] = c
            elif "HS-CODE" in c or "HS CODE" in c: col_map['HSCODE'] = c

        # Preverjanje, če imamo obvezne stolpce
        if 'CHASSIS' not in col_map:
            raise ValueError("CSV datoteka nima stolpca CHASSIS/VIN.")

        # 2. Filtriranje podatkov
        clean_chassis_input = [c.strip() for c in chassis_list if c.strip()]
        
        # Filtriramo dataframe samo na tiste šasije, ki so v inputu
        matched_df = df[df[col_map['CHASSIS']].isin(clean_chassis_input)].copy()
        
        # 3. Čiščenje in priprava podatkov v DataFrame-u
        processed_data = []
        
        for _, row in matched_df.iterrows():
            raw_dest = row.get(col_map.get('DESTINATION'), "")
            mapped_dest = self.destinations_map.get(raw_dest, raw_dest)
            final_dest = self.clean_destination(mapped_dest)
            
            weight_str = str(row.get(col_map.get('WEIGHT'), "0")).replace(',', '.')
            try:
                weight = int(float(weight_str))
            except:
                weight = 0

            processed_data.append({
                'VIN': row[col_map['CHASSIS']],
                'INVOICE': row.get(col_map.get('INVOICE'), ""),
                'DESCRIPTION': row.get(col_map.get('DESCRIPTION'), ""),
                'WEIGHT': weight,
                'DESTINATION': final_dest,
                'HS_CODE': self.clean_hs_code(row.get(col_map.get('HSCODE'), ""))
            })

        final_df = pd.DataFrame(processed_data)

        if final_df.empty:
            raise ValueError("Nobenega vozila ni bilo mogoče najti.")

        # 4. Priprava struktur za poročila (Tabs logic)
        
        # --- A) Good Items (Group by HS Code) ---
        good_items_summary = final_df.groupby('HS_CODE').agg(
            Count=('VIN', 'count'),
            TotalWeight=('WEIGHT', 'sum')
        ).reset_index()
        good_items_summary['Description'] = "NEW VEHICLES"

        # --- B) Packaging ---
        packaging_data = final_df[['VIN']].copy()
        packaging_data['Index'] = range(1, len(packaging_data) + 1)
        
        # --- C) Documents ---
        documents_data = []
        clean_diz = [d.strip() for d in diz_list if d.strip()]
        loop_range = max(len(clean_diz), 1)
        
        for i in range(loop_range):
            diz_val = clean_diz[i] if i < len(clean_diz) else ""
            documents_data.append({
                'Index': i + 1,
                'DocType': "Supporting Document",
                'DIZ_Full': f"DIZ {diz_val}" if diz_val else ""
            })

        return {
            'df': final_df,
            'good_items': good_items_summary,
            'packaging': packaging_data,
            'documents': documents_data,
            'swb_no': swb_no,
            'main_dest': final_df.iloc[0]['DESTINATION'] if not final_df.empty else "EXPORT"
        }

    def export_to_excel_buffer(self, data_pack):
        """
        Ustvari Excel datoteko v pomnilniku (BytesIO).
        """
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        workbook = writer.book
        
        # --- Stili ---
        bold_fmt = workbook.add_format({'bold': True})
        header_fmt = workbook.add_format({
            'bold': True, 
            'bg_color': '#CCFFCC', 
            'border': 1,
            'align': 'center'
        })
        
        # --- 1. Sheet: ALL VW ---
        ws_all = workbook.add_worksheet("ALL VW")
        df = data_pack['df']
        
        # Header Block
        ws_all.write(1, 1, f"ATTACHED LIST SWB NO.: {data_pack['swb_no']}", bold_fmt)
        ws_all.write(1, 2, "T2L", header_fmt)
        
        headers = ["", "VINS:", "Invoices nos.:", "DESCRIPTION", "WEIGHT", "DESTINATION", "HS CODE"]
        for col_num, header in enumerate(headers):
            ws_all.write(2, col_num, header, bold_fmt)
            
        # Zapis podatkov
        total_weight = 0
        for i, row in df.iterrows():
            row_idx = i + 3
            total_weight += row['WEIGHT']
            
            ws_all.write(row_idx, 0, i + 1)
            ws_all.write(row_idx, 1, row['VIN'])
            ws_all.write(row_idx, 2, row['INVOICE'])
            ws_all.write(row_idx, 3, row['DESCRIPTION'])
            ws_all.write(row_idx, 4, row['WEIGHT'])
            ws_all.write(row_idx, 5, row['DESTINATION'])
            ws_all.write(row_idx, 6, row['HS_CODE'])
            
        # Footer
        last_row = len(df) + 3
        ws_all.write(last_row, 4, total_weight, bold_fmt)
        
        ws_all.set_column(0, 0, 5)
        ws_all.set_column(1, 6, 20)

        # --- 2. Sheets per HS Code (Chunks of 99) ---
        unique_hs = df['HS_CODE'].unique()
        unique_hs = sorted(unique_hs)
        sheet_names_counter = {}

        for hs in unique_hs:
            hs_vehicles = df[df['HS_CODE'] == hs]
            
            chunk_size = 99
            num_chunks = (len(hs_vehicles) + chunk_size - 1) // chunk_size
            
            for i in range(num_chunks):
                chunk = hs_vehicles.iloc[i*chunk_size : (i+1)*chunk_size]
                chunk_total_weight = chunk['WEIGHT'].sum()
                
                base_name = f"{len(chunk)}x {hs}"
                sheet_name = base_name
                
                if sheet_name in sheet_names_counter:
                    sheet_names_counter[sheet_name] += 1
                    sheet_name = f"{base_name} ({sheet_names_counter[sheet_name]})"
                else:
                    sheet_names_counter[sheet_name] = 1
                    
                ws_hs = workbook.add_worksheet(sheet_name[:31])
                
                sub_headers = ["CHASSIS", "INVOICE", "DESCRIPTION", "WEIGHT", "DESTINATION", "HS CODE"]
                for c_idx, h_txt in enumerate(sub_headers):
                    ws_hs.write(0, c_idx, h_txt, bold_fmt)
                    
                r_idx = 1
                for _, row in chunk.iterrows():
                    ws_hs.write(r_idx, 0, row['VIN'])
                    ws_hs.write(r_idx, 1, row['INVOICE'])
                    ws_hs.write(r_idx, 2, row['DESCRIPTION'])
                    ws_hs.write(r_idx, 3, row['WEIGHT'])
                    ws_hs.write(r_idx, 4, row['DESTINATION'])
                    ws_hs.write(r_idx, 5, row['HS_CODE'])
                    r_idx += 1
                    
                ws_hs.write(r_idx, 3, chunk_total_weight, bold_fmt)
                ws_hs.set_column(0, 5, 20)

        writer.close()
        output.seek(0)
        return output
