import unittest
from unittest.mock import patch, MagicMock
import json
import io
import zipfile
import datetime
import sys

# Dynamic Mocking of all external dependencies
sys.modules['boto3'] = MagicMock()
sys.modules['botocore'] = MagicMock()
sys.modules['botocore.exceptions'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['google.transit'] = MagicMock()
sys.modules['google.transit.gtfs_realtime_pb2'] = MagicMock()

import os
os.environ['DYNAMO_TABLE'] = 'TestTable'

# Import the lambda_handler from the package
import lambda_function

class TestUpdateChecker(unittest.TestCase):

    def create_mock_zip(self, include_all=True, stop_count=2500, expired=False):
        """Helper to create a valid or invalid GTFS zip in memory"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            if include_all:
                z.writestr('stops.txt', 'stop_id,stop_name\n' + '\n'.join([f'{i},Stop {i}' for i in range(stop_count)]))
                z.writestr('trips.txt', 'trip_id,route_id\n1,1')
                z.writestr('stop_times.txt', 'trip_id,arrival_time,stop_id\n1,12:00:00,1')
                
                # Handle calendar date
                year = 2024 if expired else 2030
                z.writestr('calendar.txt', f'service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,1,1,20240101,{year}1231')
            else:
                z.writestr('broken.txt', 'some content')
        return buf.getvalue()

    @patch('lambda_function.requests')
    @patch('lambda_function.table')
    @patch('lambda_function.lambda_client')
    def test_no_update_needed(self, mock_lambda, mock_table, mock_requests):
        """Scenario 1: Headers match exactly, no download should happen."""
        mock_requests.head.return_value.headers = {'Last-Modified': 'Mon, 01 Jan 2026 00:00:00 GMT'}
        mock_table.get_item.return_value = {'Item': {'last_modified': 'Mon, 01 Jan 2026 00:00:00 GMT'}}

        result = lambda_function.lambda_handler({}, None)
        
        self.assertEqual(result['status'], 'NO_UPDATE_NEEDED')
        mock_requests.get.assert_not_called()
        mock_lambda.invoke.assert_not_called()

    @patch('lambda_function.requests')
    @patch('lambda_function.table')
    @patch('lambda_function.lambda_client')
    def test_invalid_data_blocked(self, mock_lambda, mock_table, mock_requests):
        """Scenario 2: New file found, but it fails the 'Guardian' validation."""
        mock_requests.head.return_value.headers = {'Last-Modified': 'Tue, 02 Jan 2026 00:00:00 GMT'}
        mock_table.get_item.return_value = {'Item': {'last_modified': 'Mon, 01 Jan 2026 00:00:00 GMT'}}
        
        # Mock an invalid ZIP (missing files)
        mock_requests.get.return_value.content = self.create_mock_zip(include_all=False)

        result = lambda_function.lambda_handler({}, None)
        
        self.assertEqual(result['status'], 'INVALID_DATA')
        self.assertIn("Missing required file", result['reason'])
        # Ensure it LOGGED the block
        mock_lambda.invoke.assert_called_with(
            FunctionName="GRT_Logger",
            InvocationType='Event',
            Payload=unittest.mock.ANY
        )

    @patch('lambda_function.requests')
    @patch('lambda_function.table')
    @patch('lambda_function.lambda_client')
    def test_successful_update(self, mock_lambda, mock_table, mock_requests):
        """Scenario 3: New valid file found, triggers ingestion."""
        mock_requests.head.return_value.headers = {'Last-Modified': 'Wed, 03 Jan 2026 00:00:00 GMT'}
        mock_table.get_item.return_value = {'Item': {'last_modified': 'Mon, 01 Jan 2026 00:00:00 GMT'}}
        
        # Mock a valid ZIP
        mock_requests.get.return_value.content = self.create_mock_zip()

        result = lambda_function.lambda_handler({}, None)
        
        self.assertEqual(result['status'], 'UPDATE_TRIGGERED')
        # Verify both ingestions were triggered
        self.assertEqual(mock_lambda.invoke.call_count, 3) # 1 log + 2 ingests
        mock_table.put_item.assert_called()

if __name__ == '__main__':
    unittest.main()
