import re
import pandas as pd
import io

class ToyotaDamageProcessor:
    def __init__(self):
        self.GARBAGE_HEADERS = [
            "Skladišče", "Pozicija", "Naročnik", "Kontejner", "Ladja", "B/L", "Int. št.",
            "Količina", "Teža", "Volumen", "Pakiranje", "Pripombe", "PS prihoda", "Tip dok",
            "Datum", "Vhodni carinski", "Blago", "Markacija", "Tehtanje", "SPREJET", "PAGE", "RO-RO",
            "Izdelano", "Predano", "Sprejeto", "Zaključeno", "Podpisali", "Ura", "Stran:",
            "NO.", "VESSEL", "DESTINATION", "VCP", "MODEL", "WEIGHT", "MOT", "LF", "DATE", "MRN", "DIZ", "DAMAGE", "PO LUŠKIH"
        ]
        
        self.FORBIDDEN_STRINGS = [
            "90 - FRAME 10 - STAINED OR SOILED 05 - OVER 30 CM IN LENGTH/DIAMETER",
            "90 - FRAME 30 - FLUID SPILLAGE, EXTERIOR (OIL SPILLAGE, BIRD DROP, OTH.) 05 - OVER 30 CM IN LENGTH/DIAMETER",
            "90 - FRAME 30 - FLUID SPILLAGE, EXTERIOR",
            "BI"
        ]

    def clean_string(self, text):
        return re.sub(r'\s+', ' ', text).strip()

    def is_garbage(self, line):
        if len(line) < 2: return True
        if line.strip() == "BI": return True
        lower_line = line.lower()
        if any(h.lower() in lower_line for h in self.GARBAGE_HEADERS): return True
        if re.search(r'PAGE\s+\d+', line): return True
        if re.match(r'^\d{1,3}(\.\d{3})*,\d{2}$', line.strip()): return True
        return False

    def is_table_row(self, line):
        # Preveri, če je vrstica del tabele iz PDF-ja (npr. začne se s številko in ima VIN)
        return re.match(r'^\s*\d+[.,]?\s+[A-Z0-9]{17}', line)

    def is_dimension_line(self, line):
        # Preveri, če je vrstica nadaljevanje opisa (dimenzije)
        dim_regex = r'^(0[0-6])\s*-\s*(?:cm|mm|missing|manjka|fehlt|up to|over|nad|do|-)'
        text_regex = r'^(?:up to|over|nad|do)\b'
        conflict_words = ["antenna", "battery", "bumper", "vrata", "door", "odbijač", "baterija", "antena", "fender", "blatnik"]
        
        lower_line = line.lower()
        has_conflict = any(w in lower_line for w in conflict_words)

        if re.match(dim_regex, line, re.IGNORECASE) and not has_conflict: return True
        if re.match(text_regex, line, re.IGNORECASE): return True
        return False

    def extract_vin(self, line, require_zp):
        clean = line.strip()
        # ZP logika (skrite napake)
        zp_match = re.search(r'ZP\s*:?\s*([A-Z0-9]{17})\b', clean, re.IGNORECASE)
        if zp_match: return zp_match.group(1)

        if not require_zp:
            # Navaden VIN (mora imeti vsaj eno črko in eno številko da ni datum/teža)
            match = re.search(r'\b([A-Z0-9]{17})\b', clean, re.IGNORECASE)
            if match:
                v = match.group(1)
                if any(c.isdigit() for c in v) and any(c.isalpha() for c in v):
                    return v
        return None

    def process_raw_text(self, raw_text):
        """Glavna funkcija za parsanje PDF teksta"""
        processed_data = {} # {VIN: [damage_lines]}
        
        # Združi inpute in preveri ZP način
        has_zp = bool(re.search(r'ZP\s*:?', raw_text, re.IGNORECASE))
        lines = raw_text.split('\n')
        
        current_vin = None
        
        for line in lines:
            trimmed = re.sub(r'ZA SKRITE NAPAKE LUKA NE ODGOVARJA\.?', '', line, flags=re.IGNORECASE).strip()
            
            # Reset checks
            if re.match(r'^VIN:|^Št\. VIN', trimmed) or self.is_table_row(trimmed) or self.is_garbage(trimmed):
                current_vin = None
                if self.is_garbage(trimmed): continue

            # Extract VIN
            vin = self.extract_vin(trimmed, has_zp)
            
            # ZP Guard: če smo v ZP mode in najdemo VIN brez ZP, je to verjetno vrstica tabele
            if has_zp and not vin and re.search(r'[A-Z0-9]{17}', trimmed):
                current_vin = None
                continue

            if vin:
                if self.is_table_row(trimmed):
                    current_vin = None
                    continue
                    
                current_vin = vin
                if current_vin not in processed_data:
                    processed_data[current_vin] = []
                
                # Očisti VIN iz vrstice, da ostane samo poškodba
                damage_part = trimmed
                damage_part = re.sub(r'^ZP\s*:?\s*', '', damage_part, flags=re.IGNORECASE)
                damage_part = damage_part.replace(current_vin, '').strip()
                damage_part = re.sub(r'^:\s*', '', damage_part)
                
                if damage_part:
                    processed_data[current_vin].append(damage_part)
            
            elif current_vin and trimmed:
                # Nadaljevanje opisa za trenutni VIN
                processed_data[current_vin].append(trimmed)

        # Post-processing: Merging lines & Cleaning
        final_results = {}
        
        for vin, raw_lines in processed_data.items():
            merged_list = []
            current_damage = ""
            
            for i, line in enumerate(raw_lines):
                # Čiščenje kod operaterjev
                line = line.replace("O:", "").replace("PT", "").strip()
                line = self.clean_string(line)
                
                if i == 0:
                    current_damage = line
                else:
                    prev_ends_hyphen = current_damage.strip().endswith('-')
                    starts_with_code = re.match(r'^\d{2}[\s-]', line)
                    looks_like_dim = self.is_dimension_line(line)
                    
                    if prev_ends_hyphen or looks_like_dim or not starts_with_code:
                        current_damage += " " + line
                    else:
                        merged_list.append(current_damage)
                        current_damage = line
            
            if current_damage:
                merged_list.append(current_damage)
            
            # Final filtering of forbidden strings
            clean_damages = []
            for d in merged_list:
                d_clean = d
                for forbidden in self.FORBIDDEN_STRINGS:
                    d_clean = d_clean.replace(forbidden, '').strip()
                
                d_clean = self.clean_string(d_clean)
                # Odstrani timestamp na koncu če obstaja (npr. 12:45)
                d_clean = re.sub(r'\s+\d+:?$', '', d_clean)
                
                if len(d_clean) > 1:
                    clean_damages.append(d_clean)
            
            if clean_damages:
                final_results[vin] = clean_damages

        return final_results

    def process_manifest_reorder(self, manifest_text, parsed_data, vin_order_list=None):
        """Reorder logic based on Manifest (Step 3 in HTML), optionally sorting by VIN list."""
        lines = manifest_text.splitlines()
        
        # Detect delimiter
        delimiter = '\t'
        for i in range(min(len(lines), 5)):
            if '\t' in lines[i]: delimiter = '\t'; break
            if ',' in lines[i]: delimiter = ','; break
            if ';' in lines[i]: delimiter = ';'; break
            
        vin_regex = re.compile(r'\b([A-Z0-9]{17})\b', re.IGNORECASE)
        
        output_rows = []
        damage_start_idx = 12 # Default M column (Index 12)
        
        # Pass 1: Header detection
        if lines:
            header_cells = lines[0].split(delimiter)
            for idx, cell in enumerate(header_cells):
                if 'DAMAGE' in cell.upper() or 'POŠKODBE' in cell.upper():
                    damage_start_idx = idx
                    break

        # Pass 2: Parsing Rows
        rows_by_vin = {}
        unmatched_rows = []

        for line in lines:
            clean_line = line.strip()
            if not clean_line: continue
            cells = [c.strip() for c in clean_line.split(delimiter)]
            
            # Find VIN in row
            found_vin = None
            for cell in cells:
                match = vin_regex.search(cell)
                if match:
                    v = match.group(1)
                    if any(c.isdigit() for c in v) and any(c.isalpha() for c in v):
                        found_vin = v
                        break
            
            row_data = {'cells': cells, 'damages': []}
            
            if found_vin:
                # Check normal or uppercase VIN
                damages = parsed_data.get(found_vin, parsed_data.get(found_vin.upper(), []))
                row_data['damages'] = damages
                # Store for reordering (normalize VIN for key)
                rows_by_vin[found_vin.upper()] = row_data
            
            # Keep original order if no specific reordering requested OR as fallback
            if not found_vin or not vin_order_list:
                output_rows.append(row_data)

        # Pass 3: Reordering (if requested)
        if vin_order_list:
            ordered_output = []
            seen_vins = set()
            
            # 1. Add requested VINs in order
            for req_vin in vin_order_list:
                req_vin = req_vin.strip().upper()
                if not req_vin: continue
                
                if req_vin in rows_by_vin:
                    ordered_output.append(rows_by_vin[req_vin])
                    seen_vins.add(req_vin)
                else:
                    # Optional: Create a dummy row for missing VIN? 
                    # For now, we skip or could insert a placeholder.
                    # User asked to "paste chassis to arrange in my order".
                    pass
            
            # 2. Add remaining VINs found in manifest but not in list (optional append)
            # usually if reordering is requested, we only want those, OR we put the rest at bottom.
            # Let's put rest at bottom to avoid data loss.
            for v, row in rows_by_vin.items():
                if v not in seen_vins:
                    ordered_output.append(row)
                    
            # 3. Add rows without VINs (Headers, Garbage) at the TOP usually, but here we likely processed them.
            # Strategy: If reordering, we assume the user provided a pure list of cars.
            # But the manifest has a header. We should preserve the header.
            # Simple heuristic: The first row of original `output_rows` is likely header.
            if output_rows and not vin_regex.search(str(output_rows[0]['cells'])):
                 ordered_output.insert(0, output_rows[0])
            
            return ordered_output, damage_start_idx
            
        return output_rows, damage_start_idx

    def inject_manual_damages(self, output_rows, manual_text):
        """Parses manual text (VIN: Damage) and injects into rows."""
        lines = manual_text.splitlines()
        manual_map = {}
        for line in lines:
            if ':' in line:
                parts = line.split(':', 1)
                vin = parts[0].strip().upper()
                dmg = parts[1].strip()
                if vin and dmg:
                    if vin not in manual_map: manual_map[vin] = []
                    manual_map[vin].append(dmg)
        
        if not manual_map: return
        
        vin_regex = re.compile(r'\b([A-Z0-9]{17})\b', re.IGNORECASE)
        
        for row in output_rows:
            # Detect VIN in row cells
            found_vin = None
            for cell in row['cells']:
                match = vin_regex.search(str(cell))
                if match:
                    found_vin = match.group(1).upper()
                    break
            
            if found_vin and found_vin in manual_map:
                row['damages'].extend(manual_map[found_vin])

    def export_excel(self, output_rows, damage_start_idx, filename):
        """Exports the reordered manifest with damages injected"""
        # Determine max columns needed
        max_cols = 0
        for r in output_rows:
            # Original length + damages length (considering overlap at start index)
            needed = max(len(r['cells']), damage_start_idx + len(r['damages']))
            max_cols = max(max_cols, needed)
            
        final_data = []
        
        for r in output_rows:
            row = r['cells'] + [''] * (max_cols - len(r['cells']))
            for i, dmg in enumerate(r['damages']):
                target_idx = damage_start_idx + i
                if target_idx < len(row):
                    row[target_idx] = dmg
                else:
                    row.append(dmg)
            final_data.append(row)
            
        df = pd.DataFrame(final_data)
        
        # Create Excel with formatting (Red text for damages)
        writer = pd.ExcelWriter(filename, engine='xlsxwriter')
        df.to_excel(writer, index=False, header=False, sheet_name='Final')
        
        workbook = writer.book
        worksheet = writer.sheets['Final']
        red_format = workbook.add_format({'font_color': '#C00000', 'bold': True})
        
        # Apply conditional formatting or iterate to set format
        # Since xlsxwriter writes data when to_excel is called, we need to overwrite cells or use conditional formatting
        # Easier approach: Write manually
        
        worksheet = workbook.add_worksheet('Formatted')
        for r_idx, r_data in enumerate(final_data):
            # Check if this row had damages
            damages = output_rows[r_idx]['damages']
            damage_indices = [damage_start_idx + i for i in range(len(damages))]
            
            for c_idx, cell_val in enumerate(r_data):
                if c_idx in damage_indices and cell_val in damages:
                    worksheet.write(r_idx, c_idx, cell_val, red_format)
                else:
                    worksheet.write(r_idx, c_idx, cell_val)
                    
        writer.close()
        # Return buffer or stream? The original logic returned filename.
        # But we would likely want to return bytes buffer for web.
        # For now, sticking to logic provided, assuming file system write.
        # We might need to adapter this for Flask send_file later.
        return filename
