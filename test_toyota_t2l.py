
import pandas as pd
import io
import unittest
from toyota_t2l_utils import ToyotaAttListaHelper

class TestToyotaT2L(unittest.TestCase):
    def test_processing(self):
        # 1. Create Dummy CSV content
        csv_content = """VIN;DESTINATION;DVH;MODEL;WEIGHT
        VIN12345;EGYAG;INV001;COROLLA;1500
        VIN67890;LIMA;INV002;YARIS;1200
        VIN11111;UNKNOWN;INV003;CAMRY;1600
        """
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        
        # 2. Setup Inputs
        chassis_list = ["VIN12345", "VIN67890"] # VIN11111 is ignored
        diz_list = ["DIZ001"]
        swb_no = "TEST_SWB"
        
        # 3. Process
        helper = ToyotaAttListaHelper()
        data = helper.load_and_process(csv_file, chassis_list, diz_list, swb_no)
        
        # 4. Verify Data
        df = data['df']
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]['VIN'], 'VIN12345')
        self.assertEqual(df.iloc[0]['DESTINATION'], 'ALEXANDRIA') # Cleaned destination
        self.assertEqual(df.iloc[1]['DESTINATION'], 'LIMASSOL')
        
        # 5. Verify Excel Generation
        excel_buffer = helper.export_to_excel_buffer(data)
        self.assertTrue(excel_buffer.getbuffer().nbytes > 0)
        print("Excel generated successfully, size:", excel_buffer.getbuffer().nbytes)

if __name__ == '__main__':
    unittest.main()
