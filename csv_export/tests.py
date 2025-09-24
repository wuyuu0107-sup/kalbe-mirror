import json
import csv
from io import StringIO
from django.test import TestCase, Client
from django.urls import reverse


class CSVExportTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.valid_ocr_data = {
            "results": [
                {
                    "text": "Sample Text 1",
                    "confidence": 0.95,
                    "box": [[10, 20], [100, 20], [100, 50], [10, 50]]
                },
                {
                    "text": "Sample Text 2", 
                    "confidence": 0.87,
                    "box": [[200, 300], [400, 300], [400, 350], [200, 350]]
                }
            ]
        }

#     def test_csv_export_page_renders(self):
#         """Test that the CSV export page renders successfully"""
#         response = self.client.get('/export/')
#         self.assertEqual(response.status_code, 200)
#         self.assertContains(response, 'Export OCR Results to CSV')
#         self.assertContains(response, 'Paste your OCR JSON results here:')

#     def test_export_ocr_csv_with_valid_data(self):
#         """Test CSV export with valid OCR data"""
#         response = self.client.post(
#             '/export/ocr/',
#             data=json.dumps(self.valid_ocr_data),
#             content_type='application/json'
#         )
        
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(response['Content-Type'], 'text/csv')
#         self.assertEqual(
#             response['Content-Disposition'], 
#             'attachment; filename="ocr_results.csv"'
#         )
        
#         # Parse CSV content
#         csv_content = response.content.decode('utf-8')
#         reader = csv.reader(StringIO(csv_content))
#         rows = list(reader)
        
#         # Check headers
#         expected_headers = [
#             'Text', 'Confidence', 'Box_X1', 'Box_Y1', 'Box_X2', 'Box_Y2',
#             'Box_X3', 'Box_Y3', 'Box_X4', 'Box_Y4'
#         ]
#         self.assertEqual(rows[0], expected_headers)
        
#         # Check first data row
#         self.assertEqual(rows[1][0], 'Sample Text 1')
#         self.assertEqual(rows[1][1], '0.95')
#         self.assertEqual(rows[1][2:10], ['10', '20', '100', '20', '100', '50', '10', '50'])
        
#         # Check second data row
#         self.assertEqual(rows[2][0], 'Sample Text 2')
#         self.assertEqual(rows[2][1], '0.87')
#         self.assertEqual(rows[2][2:10], ['200', '300', '400', '300', '400', '350', '200', '350'])

#     def test_export_ocr_csv_with_empty_results(self):
#         """Test CSV export with empty results"""
#         empty_data = {"results": []}
        
#         response = self.client.post(
#             '/export/ocr/',
#             data=json.dumps(empty_data),
#             content_type='application/json'
#         )
        
#         self.assertEqual(response.status_code, 200)
        
#         # Should only have headers
#         csv_content = response.content.decode('utf-8')
#         reader = csv.reader(StringIO(csv_content))
#         rows = list(reader)
        
#         self.assertEqual(len(rows), 1)  # Only header row
#         expected_headers = [
#             'Text', 'Confidence', 'Box_X1', 'Box_Y1', 'Box_X2', 'Box_Y2',
#             'Box_X3', 'Box_Y3', 'Box_X4', 'Box_Y4'
#         ]
#         self.assertEqual(rows[0], expected_headers)

#     def test_export_ocr_csv_with_incomplete_box_data(self):
#         """Test CSV export with incomplete bounding box data"""
#         incomplete_data = {
#             "results": [
#                 {
#                     "text": "Incomplete Box",
#                     "confidence": 0.75,
#                     "box": [[10, 20], [100, 20]]  # Only 2 points instead of 4
#                 }
#             ]
#         }
        
#         response = self.client.post(
#             '/export/ocr/',
#             data=json.dumps(incomplete_data),
#             content_type='application/json'
#         )
        
#         self.assertEqual(response.status_code, 200)
        
#         csv_content = response.content.decode('utf-8')
#         reader = csv.reader(StringIO(csv_content))
#         rows = list(reader)
        
#         # Check that missing coordinates are filled with empty strings
#         self.assertEqual(rows[1][0], 'Incomplete Box')
#         self.assertEqual(rows[1][1], '0.75')
#         self.assertEqual(rows[1][2:6], ['10', '20', '100', '20'])
#         self.assertEqual(rows[1][6:10], ['', '', '', ''])  # Empty padding

#     def test_export_ocr_csv_with_missing_fields(self):
#         """Test CSV export with missing text or confidence fields"""
#         missing_fields_data = {
#             "results": [
#                 {
#                     "text": "Text Only",
#                     "box": [[0, 0], [10, 0], [10, 10], [0, 10]]
#                     # Missing confidence
#                 },
#                 {
#                     "confidence": 0.88,
#                     "box": [[20, 20], [30, 20], [30, 30], [20, 30]]
#                     # Missing text
#                 }
#             ]
#         }
        
#         response = self.client.post(
#             '/export/ocr/',
#             data=json.dumps(missing_fields_data),
#             content_type='application/json'
#         )
        
#         self.assertEqual(response.status_code, 200)
        
#         csv_content = response.content.decode('utf-8')
#         reader = csv.reader(StringIO(csv_content))
#         rows = list(reader)
        
#         # First row - missing confidence
#         self.assertEqual(rows[1][0], 'Text Only')
#         self.assertEqual(rows[1][1], '0')  # Default confidence
        
#         # Second row - missing text
#         self.assertEqual(rows[2][0], '')  # Default empty text
#         self.assertEqual(rows[2][1], '0.88')

#     def test_export_ocr_csv_with_invalid_json(self):
#         """Test CSV export with invalid JSON"""
#         response = self.client.post(
#             '/export/ocr/',
#             data='invalid json',
#             content_type='application/json'
#         )
        
#         self.assertEqual(response.status_code, 400)
#         self.assertIn('Error:', response.content.decode('utf-8'))

#     def test_export_ocr_csv_get_method_not_allowed(self):
#         """Test that GET method is not allowed for CSV export"""
#         response = self.client.get('/export/ocr/')
#         self.assertEqual(response.status_code, 405)  # Method not allowed

#     def test_export_ocr_csv_without_results_key(self):
#         """Test CSV export with data missing 'results' key"""
#         invalid_data = {"data": "some data"}
        
#         response = self.client.post(
#             '/export/ocr/',
#             data=json.dumps(invalid_data),
#             content_type='application/json'
#         )
        
#         self.assertEqual(response.status_code, 200)
        
#         # Should only have headers since no results
#         csv_content = response.content.decode('utf-8')
#         reader = csv.reader(StringIO(csv_content))
#         rows = list(reader)
        
#         self.assertEqual(len(rows), 1)  # Only header row

#     def test_csv_export_large_dataset(self):
#         """Test CSV export with a large dataset"""
#         large_data = {
#             "results": []
#         }
        
#         # Generate 100 OCR results
#         for i in range(100):
#             large_data["results"].append({
#                 "text": f"Text {i}",
#                 "confidence": 0.9 + (i % 10) * 0.01,
#                 "box": [[i, i+10], [i+50, i+10], [i+50, i+40], [i, i+40]]
#             })
        
#         response = self.client.post(
#             '/export/ocr/',
#             data=json.dumps(large_data),
#             content_type='application/json'
#         )
        
#         self.assertEqual(response.status_code, 200)
        
#         csv_content = response.content.decode('utf-8')
#         reader = csv.reader(StringIO(csv_content))
#         rows = list(reader)
        
#         # Should have header + 100 data rows
#         self.assertEqual(len(rows), 101)
        
#         # Check first and last data rows
#         self.assertEqual(rows[1][0], 'Text 0')
#         self.assertEqual(rows[100][0], 'Text 99')

#     def test_csv_export_special_characters(self):
#         """Test CSV export with special characters in text"""
#         special_char_data = {
#             "results": [
#                 {
#                     "text": "Text with, commas and \"quotes\"",
#                     "confidence": 0.95,
#                     "box": [[0, 0], [100, 0], [100, 30], [0, 30]]
#                 },
#                 {
#                     "text": "Unicode: 中文, émojis: 🔥",
#                     "confidence": 0.87,
#                     "box": [[0, 40], [100, 40], [100, 70], [0, 70]]
#                 }
#             ]
#         }
        
#         response = self.client.post(
#             '/export/ocr/',
#             data=json.dumps(special_char_data),
#             content_type='application/json'
#         )
        
#         self.assertEqual(response.status_code, 200)
        
#         csv_content = response.content.decode('utf-8')
#         reader = csv.reader(StringIO(csv_content))
#         rows = list(reader)
        
#         # CSV should properly handle special characters
#         self.assertEqual(rows[1][0], 'Text with, commas and "quotes"')
#         self.assertEqual(rows[2][0], 'Unicode: 中文, émojis: 🔥')