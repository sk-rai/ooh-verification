"""
CSV Processing Service for bulk operations.

Requirements:
- Req 2.1-2.6: Bulk campaign operations
- Req 3.1-3.10: Bulk vendor operations
- Req 4.1-4.11: Bulk assignment operations
- Property 6: Bulk import correctness
- Property 7: CSV structure validation
"""

import csv
import io
import logging
from typing import List, Dict, Any, Tuple, Optional
from fastapi import UploadFile
from datetime import datetime

from app.schemas.assignment import BulkOperationRow, BulkOperationResponse

logger = logging.getLogger(__name__)


class CSVProcessor:
    """Service for processing CSV files for bulk operations."""
    
    CAMPAIGN_REQUIRED_COLUMNS = ['name', 'campaign_type', 'start_date', 'end_date']
    CAMPAIGN_OPTIONAL_COLUMNS = ['address', 'latitude', 'longitude', 'location_name']
    
    VENDOR_REQUIRED_COLUMNS = ['name', 'phone_number']
    VENDOR_OPTIONAL_COLUMNS = ['email']
    
    ASSIGNMENT_REQUIRED_COLUMNS = ['campaign_code', 'vendor_id']
    ASSIGNMENT_OPTIONAL_COLUMNS = ['address', 'latitude', 'longitude', 'location_name']
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_ROWS_CAMPAIGNS = 10000
    MAX_ROWS_VENDORS = 10000
    MAX_ROWS_ASSIGNMENTS = 50000
    
    async def validate_csv_structure(
        self,
        file: UploadFile,
        required_columns: List[str],
        optional_columns: List[str] = None
    ) -> Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Validate CSV file structure and parse rows.
        
        Requirements:
        - Property 7: CSV structure validation
        - Property 12: Character encoding preservation
        - Property 22: CSV quoted field handling
        
        Returns:
            Tuple of (is_valid, error_message, parsed_rows)
        """
        try:
            # Check file size
            content = await file.read()
            if len(content) > self.MAX_FILE_SIZE:
                return False, f"File size exceeds {self.MAX_FILE_SIZE / 1024 / 1024}MB limit", None
            
            # Reset file pointer
            await file.seek(0)
            
            # Try to decode as UTF-8
            try:
                text_content = content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    text_content = content.decode('utf-8-sig')  # Try with BOM
                except UnicodeDecodeError:
                    return False, "File must be UTF-8 encoded", None
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(text_content))
            
            # Validate headers
            if not csv_reader.fieldnames:
                return False, "CSV file is empty or has no headers", None
            
            # Check required columns
            missing_columns = set(required_columns) - set(csv_reader.fieldnames)
            if missing_columns:
                return False, f"Missing required columns: {', '.join(missing_columns)}", None
            
            # Parse all rows
            rows = []
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (1 is header)
                # Trim whitespace from all values
                trimmed_row = {k: v.strip() if v else v for k, v in row.items()}
                rows.append({
                    'row_number': row_num,
                    'data': trimmed_row
                })
            
            if not rows:
                return False, "CSV file has no data rows", None
            
            return True, None, rows
            
        except csv.Error as e:
            return False, f"CSV parsing error: {str(e)}", None
        except Exception as e:
            logger.error(f"Unexpected error validating CSV: {e}")
            return False, f"Error processing CSV file: {str(e)}", None
    
    def detect_duplicates_in_csv(
        self,
        rows: List[Dict[str, Any]],
        key_field: str
    ) -> Dict[str, List[int]]:
        """
        Detect duplicate values in CSV rows.
        
        Requirements:
        - Property 8: Intra-file duplicate detection
        
        Returns:
            Dict mapping duplicate values to list of row numbers
        """
        seen = {}
        duplicates = {}
        
        for row in rows:
            value = row['data'].get(key_field)
            if not value:
                continue
            
            if value in seen:
                if value not in duplicates:
                    duplicates[value] = [seen[value]]
                duplicates[value].append(row['row_number'])
            else:
                seen[value] = row['row_number']
        
        return duplicates
    
    def validate_date_format(self, date_str: str) -> Tuple[bool, Optional[str], Optional[datetime]]:
        """
        Validate date is in ISO 8601 format (YYYY-MM-DD).
        
        Requirements:
        - Property 19: Date format validation
        """
        if not date_str:
            return False, "Date is required", None
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return True, None, date_obj
        except ValueError:
            return False, f"Invalid date format: {date_str}. Expected YYYY-MM-DD", None
    
    def validate_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate start_date is before end_date.
        
        Requirements:
        - Property 20: Date range validation
        """
        if start_date >= end_date:
            return False, f"Start date ({start_date.date()}) must be before end date ({end_date.date()})"
        return True, None
    
    def validate_coordinates(
        self,
        latitude: Optional[str],
        longitude: Optional[str]
    ) -> Tuple[bool, Optional[str], Optional[float], Optional[float]]:
        """
        Validate latitude and longitude coordinates.
        
        Requirements:
        - Property 39: Location data validation
        """
        # If neither provided, that's ok
        if not latitude and not longitude:
            return True, None, None, None
        
        # If one provided, both must be provided
        if bool(latitude) != bool(longitude):
            return False, "Both latitude and longitude must be provided together", None, None
        
        try:
            lat = float(latitude)
            lon = float(longitude)
            
            if lat < -90 or lat > 90:
                return False, f"Latitude must be between -90 and 90, got {lat}", None, None
            
            if lon < -180 or lon > 180:
                return False, f"Longitude must be between -180 and 180, got {lon}", None, None
            
            return True, None, lat, lon
            
        except ValueError:
            return False, f"Invalid coordinate format: lat={latitude}, lon={longitude}", None, None
    
    def create_error_row(
        self,
        row_number: int,
        error_message: str
    ) -> BulkOperationRow:
        """Create an error result row."""
        return BulkOperationRow(
            row=row_number,
            status="error",
            error=error_message
        )
    
    def create_success_row(
        self,
        row_number: int,
        data: Dict[str, Any]
    ) -> BulkOperationRow:
        """Create a success result row."""
        return BulkOperationRow(
            row=row_number,
            status="success",
            data=data
        )


class CSVProcessingError(Exception):
    """Raised when CSV processing fails."""
    pass
