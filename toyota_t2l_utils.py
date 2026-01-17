import pandas as pd
import re
import io
import xlsxwriter

class ToyotaAttListaHelper:
    def __init__(self):
        # Destinacije (enako kot pri VW)
        self.destinations_map = {
            "EGYAG": "ALEXANDRIA (EGIPT)", "AZEMQ": "AZERBAIJAN", "CYPEY": "LIMASSOL (CIPER)",
            "GEODB": "GEORGIA", "CYPXP": "LIMASSOL (CIPER)", "CYPEZ": "NORTH CYPRUS",
            "GRCGR": "PIRAEUS (GRČIJA)", "GRCDP": "PIRAEUS (GRČIJA)", "ILASH": "HAIFA",
            "ILHFA": "HAIFA", "ILPAL": "PALESTINA (HAIFA)", "LBNLJ": "BEIRUT",
            "MTSGW": "LA VALLETTA (MALTA)", "TNTUN": "LA GOULLETE (TUNISIJA)", 
            "TREYP": "EFESAN (TURČIJA)", "LIMA": "LIMASSOL (CIPER)", "PIRE": "PIRAEUS (GRČIJA)"
        }

    def clean_destination(self, name):
        if not name: return ""
        return re.sub(r'\s*\(.*?\)\s*', '', str(name)).strip()

    def clean_hs_code(self, code):
        """Očisti HS kodo."""
        if not code: return "TOYOTA" # Privzeto za Toyoto, če ni podana
        code = str(code).strip()
        clean = re.sub(r'[^a-zA-Z0-9]', '', code)
        if len(clean) >= 6 and clean.isdigit():
            return clean[:6]
        return clean

    def load_and_process(self, csv_file_obj, chassis_list, diz_list, swb_no, manual_hs_codes=None):
        """
        Inputs:
            csv_file_obj: file object or path to TOYOTA Stock CSV
            chassis_list: seznam VIN številk
            diz_list: seznam DIZ številk
            swb_no: SWB številka
            manual_hs_codes: Slovar {VIN: HS_CODE}, ki ga uporabnik vnese ročno
        """
        if manual_hs_codes is None:
            manual_hs_codes = {}

        # 1. Branje CSV
        try:
            df = pd.read_csv(csv_file_obj, sep=';', on_bad_lines='skip', dtype=str)
        except:
            if hasattr(csv_file_obj, 'seek'):
                csv_file_obj.seek(0)
            df = pd.read_csv(csv_file_obj, sep=',', on_bad_lines='skip', dtype=str)

        df.columns = [c.strip().upper() for c in df.columns]

        # 2. Mapiranje stolpcev (Specifično za TOYOTA)
        col_map = {}
        for c in df.columns:
            if "VIN" in c: col_map['CHASSIS'] = c
            elif "DESTINATION" in c: col_map['DESTINATION'] = c
            elif "DVH" in c: col_map['INVOICE'] = c      # Toyota uporablja DVH za Invoice
            elif "MODEL" in c: col_map['DESCRIPTION'] = c # Toyota uporablja MODEL za Description
            elif "WEIGHT" in c: col_map['WEIGHT'] = c
        
        if 'CHASSIS' not in col_map:
            raise ValueError("CSV datoteka nima stolpca VIN/CHASSIS.")

        # 3. Filtriranje in obdelava
        clean_chassis_input = [c.strip() for c in chassis_list if c.strip()]
        
        # Filtriranje DataFrame-a
        matched_df = df[df[col_map['CHASSIS']].isin(clean_chassis_input)].copy()
        
        # Opozorilo za manjkajoče
        found_vins = set(matched_df[col_map['CHASSIS']])
        missing_vins = set(clean_chassis_input) - found_vins
        if missing_vins:
            print(f"OPOZORILO: Naslednje šasije niso bile najdene: {missing_vins}")

        processed_data = []

        for _, row in matched_df.iterrows():
            vin = row[col_map['CHASSIS']]
            
            # Destinacija
            raw_dest = row.get(col_map.get('DESTINATION'), "")
            mapped_dest = self.destinations_map.get(raw_dest, raw_dest)
            final_dest = self.clean_destination(mapped_dest)
            
            # Teža
            weight_str = str(row.get(col_map.get('WEIGHT'), "0")).replace(',', '.')
            try: weight = int(float(weight_str))
            except: weight = 0

            # HS Koda (Logika: Ročni vnos > Default "TOYOTA")
            hs_code = "TOYOTA"
            if vin in manual_hs_codes:
                hs_code = self.clean_hs_code(manual_hs_codes[vin])
            
            processed_data.append({
                'VIN': vin,
                'INVOICE': row.get(col_map.get('INVOICE'), ""),
                'DESCRIPTION': row.get(col_map.get('DESCRIPTION'), ""),
                'WEIGHT': weight,
                'DESTINATION': final_dest,
                'HS_CODE': hs_code
            })

        final_df = pd.DataFrame(processed_data)

        if final_df.empty:
            raise ValueError("Nobenega vozila ni bilo mogoče najti.")

        # 4. Priprava za Excel (Good Items / Packaging / Docs)
        
        # Good Items
        good_items_summary = final_df.groupby('HS_CODE').agg(
            Count=('VIN', 'count'),
            TotalWeight=('WEIGHT', 'sum')
        ).reset_index()
        good_items_summary['Description'] = "NEW VEHICLES"

        # Packaging (Toyota logika je enaka VW - 1 vozilo = 1 paket)
        packaging_data = final_df[['VIN']].copy()
        packaging_data['Index'] = range(1, len(packaging_data) + 1)
        packaging_data['VN1'] = "VN - Vehicle"
        packaging_data['Qty'] = 1

        # Documents
        clean_diz = [d.strip() for d in diz_list if d.strip()]
        documents_data = []
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
        """Adapted for Flask: returns io.BytesIO"""
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        workbook = writer.book
        
        # Stili
        bold_fmt = workbook.add_format({'bold': True})
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#CCFFCC', 'border': 1, 'align': 'center'
        })
        
        # --- 1. Sheet: ALL TOYOTA ---
        ws_all = workbook.add_worksheet("ALL TOYOTA")
        df = data_pack['df']
        
        # Header
        ws_all.write(1, 1, f"ATTACHED LIST SWB NO.: {data_pack['swb_no']}", bold_fmt)
        ws_all.write(1, 2, "T2L", header_fmt)
        
        headers = ["", "VINS:", "Invoices nos.:", "DESCRIPTION", "WEIGHT", "DESTINATION", "HS CODE"]
        for c, h in enumerate(headers):
            ws_all.write(2, c, h, bold_fmt)
            
        total_weight = 0
        for i, row in df.iterrows():
            r = i + 3
            total_weight += row['WEIGHT']
            ws_all.write(r, 0, i + 1)
            ws_all.write(r, 1, row['VIN'])
            ws_all.write(r, 2, row['INVOICE'])
            ws_all.write(r, 3, row['DESCRIPTION'])
            ws_all.write(r, 4, row['WEIGHT'])
            ws_all.write(r, 5, row['DESTINATION'])
            ws_all.write(r, 6, row['HS_CODE'])
            
        ws_all.write(len(df) + 3, 4, total_weight, bold_fmt)
        ws_all.set_column(1, 6, 20)

        # --- 2. Sheets per HS Code (Chunks) ---
        unique_hs = sorted(df['HS_CODE'].unique())
        sheet_names_counter = {}

        for hs in unique_hs:
            hs_vehicles = df[df['HS_CODE'] == hs]
            chunk_size = 99
            num_chunks = (len(hs_vehicles) + chunk_size - 1) // chunk_size
            
            for i in range(num_chunks):
                chunk = hs_vehicles.iloc[i*chunk_size : (i+1)*chunk_size]
                chunk_weight = chunk['WEIGHT'].sum()
                
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
                
                ws_hs.write(r_idx, 3, chunk_weight, bold_fmt)
                ws_hs.set_column(0, 5, 20)

        writer.close()
        output.seek(0)
        return output
