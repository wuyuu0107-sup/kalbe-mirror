import os
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from save_to_database.models import CSV


class SignalTests(TestCase):
    def setUp(self):
        self.sample_json = [
            {
                "id": 1,
                "name": "John Doe",
                "contact": {
                    "email": "john@example.com",
                    "phone": "+1-555-0123"
                }
            }
        ]
        self.csv_file = SimpleUploadedFile("test.csv", b"id,name\n1,John", content_type="text/csv")

    def test_signal_skips_when_upload_disabled(self):
        """Signal should skip upload when SUPABASE_UPLOAD_ENABLED is False."""
        with patch.dict(os.environ, {'SUPABASE_UPLOAD_ENABLED': 'false'}, clear=False):
            with patch('save_to_database.signals.logger') as mock_logger:
                CSV.objects.create(
                    name="test-dataset",
                    file=self.csv_file,
                    source_json=self.sample_json
                )
                mock_logger.debug.assert_called_with("Skipping upload: SUPABASE_UPLOAD_ENABLED not set")

    def test_signal_skips_when_no_source_json(self):
        """Signal should skip when source_json is None."""
        with patch('save_to_database.signals.json_to_csv_bytes') as mock_convert:
            CSV.objects.create(
                name="test-dataset",
                file=self.csv_file,
                source_json=None
            )
            mock_convert.assert_not_called()

    @patch.dict(os.environ, {'SUPABASE_UPLOAD_ENABLED': 'true', 'SUPABASE_BUCKET': 'test-bucket'})
    @patch('save_to_database.signals.upload_csv_to_supabase')
    @patch('save_to_database.signals.json_to_csv_bytes')
    def test_successful_upload(self, mock_convert, mock_upload):
        """Signal should convert and upload when conditions are met."""
        mock_convert.return_value = b"id,name\n1,John Doe"
        mock_upload.return_value = "https://example.com/test.csv"
        
        csv_record = CSV.objects.create(
            name="test-dataset",
            file=self.csv_file,
            source_json=self.sample_json
        )
        
        # Check the mocks were called
        mock_convert.assert_called_once_with(self.sample_json)
        mock_upload.assert_called_once()
        
        # Check database was updated (fetch fresh instance)
        updated_record = CSV.objects.get(pk=csv_record.pk)
        self.assertEqual(updated_record.uploaded_url, "https://example.com/test.csv")

    def test_signal_skips_when_no_bucket(self):
        """Signal should skip when SUPABASE_BUCKET is not set."""
        with patch.dict(os.environ, {'SUPABASE_UPLOAD_ENABLED': 'true'}, clear=False):
            # Make sure SUPABASE_BUCKET is not set
            if 'SUPABASE_BUCKET' in os.environ:
                del os.environ['SUPABASE_BUCKET']
            
            with patch('save_to_database.signals.logger') as mock_logger:
                CSV.objects.create(
                    name="test-dataset",
                    file=self.csv_file,
                    source_json=self.sample_json
                )
                mock_logger.warning.assert_called_with("SUPABASE_BUCKET not set; skipping upload")

    @patch.dict(os.environ, {'SUPABASE_UPLOAD_ENABLED': 'true', 'SUPABASE_BUCKET': 'test-bucket'})
    @patch('save_to_database.signals.upload_csv_to_supabase')
    @patch('save_to_database.signals.json_to_csv_bytes')
    def test_handles_conversion_error(self, mock_convert, mock_upload):
        """Signal should handle conversion errors gracefully."""
        mock_convert.side_effect = Exception("Conversion failed")
        
        with patch('save_to_database.signals.logger') as mock_logger:
            CSV.objects.create(
                name="test-dataset",
                file=self.csv_file,
                source_json=self.sample_json
            )
            mock_logger.exception.assert_called()
            mock_upload.assert_not_called()

    @patch.dict(os.environ, {'SUPABASE_UPLOAD_ENABLED': 'true', 'SUPABASE_BUCKET': 'test-bucket'})
    @patch('save_to_database.signals.upload_csv_to_supabase')
    @patch('save_to_database.signals.json_to_csv_bytes')
    def test_skips_empty_csv(self, mock_convert, mock_upload):
        """Signal should skip upload when CSV bytes are empty."""
        mock_convert.return_value = b""
        
        with patch('save_to_database.signals.logger') as mock_logger:
            CSV.objects.create(
                name="test-dataset",
                file=self.csv_file,
                source_json=self.sample_json
            )
            mock_logger.warning.assert_called_with("Converted CSV empty; skipping upload")
            mock_upload.assert_not_called()

    @patch.dict(os.environ, {'SUPABASE_UPLOAD_ENABLED': 'true', 'SUPABASE_BUCKET': 'test-bucket'})
    @patch('save_to_database.signals.upload_csv_to_supabase')
    @patch('save_to_database.signals.json_to_csv_bytes')
    def test_path_generation(self, mock_convert, mock_upload):
        """Signal should generate correct date-prefixed file paths."""
        import datetime

        mock_convert.return_value = b"test,data"
        mock_upload.return_value = "https://example.com/test.csv"

        fixed_date = datetime.date(2025, 10, 20)
        with patch('save_to_database.signals.datetime') as mock_datetime:
            mock_datetime.datetime.now.return_value = datetime.datetime(2025, 10, 20)
            mock_datetime.date = datetime.date

            csv_record = CSV.objects.create(
                name="test dataset with spaces",
                file=self.csv_file,
                source_json=self.sample_json
            )

        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        if call_args:
            args, kwargs = call_args
            if len(args) >= 3:
                actual_path = args[2]
            else:
                actual_path = kwargs.get('path', '')

            expected_name = "test_dataset_with_spaces"
            expected_path = f"csvs/{fixed_date}_{csv_record.id}_{expected_name}.csv"
            self.assertEqual(actual_path, expected_path)
        else:
            self.fail("upload_csv_to_supabase was not called with expected arguments")

    def test_signal_skips_when_url_already_exists(self):
        """Signal should skip when uploaded_url already exists."""
        with patch.dict(os.environ, {'SUPABASE_UPLOAD_ENABLED': 'true', 'SUPABASE_BUCKET': 'test-bucket'}):
            with patch('save_to_database.signals.json_to_csv_bytes') as mock_convert:
                with patch('save_to_database.signals.logger') as mock_logger:
                    CSV.objects.create(
                        name="test-dataset",
                        file=self.csv_file,
                        source_json=self.sample_json,
                        uploaded_url="https://existing-url.com/file.csv"
                    )
                    mock_logger.debug.assert_called_with("Upload URL already exists, skipping signal")
                    mock_convert.assert_not_called()