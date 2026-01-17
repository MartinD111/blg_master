import re
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import io

class ATRExtractor:
    def __init__(self):
        # Nastavitve regexov
        self.atr_prefix = "N"
        self.atr_len = 7
        self.inv_max = 6

    def repair_numbers(self, text):
        """Popravi pogoste OCR napake pri številkah (S->5, Z->2 itd.)"""
        if not text: return ""
        replacements = {'S': '5', 'Z': '2', 'O': '0', 'D': '0', 'B': '8', 'I': '1', 'l': '1', 'L': '1'}
        for char, digit in replacements.items():
            text = text.replace(char, digit)
        return text

    def extract_text(self, file_bytes, filename):
        """Izlušči tekst iz slike ali PDF"""
        text = ""
        try:
            if filename.lower().endswith('.pdf'):
                # Requires Poppler installed and in PATH
                images = convert_from_bytes(file_bytes)
                for img in images:
                    text += pytesseract.image_to_string(img) + " "
            else:
                # Obdelaj sliko
                image = Image.open(io.BytesIO(file_bytes))
                text = pytesseract.image_to_string(image)
        except Exception as e:
            print(f"Napaka pri OCR (Tesseract/Poppler install needed?): {e}")
            return "" # Return empty so analysis handles it gracefully
        return text.upper()

    def analyze_content(self, raw_text):
        """Regex logika za iskanje A.TR in Invoice"""
        text = re.sub(r'\s+', ' ', raw_text)
        result = {"atr": "Ni najdeno", "invoice": "Ni najdeno"}

        # 1. Iskanje A.TR
        text_atr_clean = re.sub(r'(?:NO|N0|NR|NUMBER)[:.]', ' ', text)
        
        atr_pattern = rf"{self.atr_prefix}\s*([0-9SZODBIL\s]{{{self.atr_len},{self.atr_len+5}}})"
        match_atr = re.search(atr_pattern, text_atr_clean)
        
        if match_atr:
            clean_num = match_atr.group(0).replace(" ", "")
            result["atr"] = self.atr_prefix + self.repair_numbers(clean_num[1:self.atr_len+1])

        # 2. Iskanje Invoice
        inv_keywords = r"INVOICE|INV|FATURA|BILL|FACTUUR|RECHNUNG|FAKTURA"
        inv_pattern = rf"(?:{inv_keywords})\s*(?:NO|N0|NUMBER|NUM|NR)?[:.]?\s*([0-9SZODBIL]{{4,{self.inv_max}}})"
        
        match_inv = re.search(inv_pattern, text)
        if match_inv:
            result["invoice"] = self.repair_numbers(re.sub(r'\s+', '', match_inv.group(1)))
        else:
            fallback_pattern = rf"(?:^|[^0-9])([0-9SZODBIL]{{4,{self.inv_max}}})(?:[^0-9]|$)"
            candidates = re.findall(fallback_pattern, text)
            
            valid_cands = []
            for c in candidates:
                num = self.repair_numbers(re.sub(r'[^0-9SZODBIL]', '', c))
                if len(num) == 4 and (num.startswith("202") or num == "1000"): continue
                if num in ["34885", "73232", "0363"]: continue
                valid_cands.append(num)

            if valid_cands:
                result["invoice"] = valid_cands[0]

        return result
