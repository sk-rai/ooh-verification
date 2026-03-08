"""
DynamoDB client configuration and table management.

Requirements:
- Req 10.1: Append-only audit log storage
- Req 10.2: Hash chaining for immutability
- Req 10.3: Tamper-evident audit trail
"""
import boto3
from botocore.exceptions import ClientError
from typing import Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class DynamoDBClient:
    """DynamoDB client wrapper for audit logging."""
    
    def __init__(self):
        """Initialize DynamoDB client with local or AWS endpoint."""
        self._client = None
        self._resource = None
        self._table = None
    
    @property
    def client(self):
        """Get or create DynamoDB client."""
        if self._client is None:
            kwargs = {
                'region_name': settings.DYNAMODB_REGION
            }
            
            # Use local endpoint for development
            if settings.DYNAMODB_ENDPOINT_URL:
                kwargs['endpoint_url'] = settings.DYNAMODB_ENDPOINT_URL
                # For local DynamoDB, we need dummy credentials
                kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID or 'dummy'
                kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY or 'dummy'
            elif settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
                kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
            
            self._client = boto3.client('dynamodb', **kwargs)
        
        return self._client
    
    @property
    def resource(self):
        """Get or create DynamoDB resource."""
        if self._resource is None:
            kwargs = {
                'region_name': settings.DYNAMODB_REGION
            }
            
            # Use local endpoint for development
            if settings.DYNAMODB_ENDPOINT_URL:
                kwargs['endpoint_url'] = settings.DYNAMODB_ENDPOINT_URL
                kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID or 'dummy'
                kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY or 'dummy'
            elif settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
                kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
                kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY
            
            self._resource = boto3.resource('dynamodb', **kwargs)
        
        return self._resource
    
    @property
    def table(self):
        """Get or create DynamoDB table reference."""
        if self._table is None:
            self._table = self.resource.Table(settings.DYNAMODB_TABLE_NAME)
        return self._table
    
    def table_exists(self) -> bool:
        """Check if the audit log table exists."""
        try:
            self.client.describe_table(TableName=settings.DYNAMODB_TABLE_NAME)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                return False
            raise
    
    def create_table(self) -> bool:
        """
        Create the audit log table with proper schema and indexes.
        
        Returns:
            bool: True if table was created, False if it already exists
        """
        if self.table_exists():
            logger.info(f"Table {settings.DYNAMODB_TABLE_NAME} already exists")
            return False
        
        try:
            table = self.resource.create_table(
                TableName=settings.DYNAMODB_TABLE_NAME,
                KeySchema=[
                    {
                        'AttributeName': 'audit_id',
                        'KeyType': 'HASH'  # Partition key
                    },
                    {
                        'AttributeName': 'timestamp',
                        'KeyType': 'RANGE'  # Sort key
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'audit_id',
                        'AttributeType': 'S'
                    },
                    {
                        'AttributeName': 'timestamp',
                        'AttributeType': 'S'
                    },
                    {
                        'AttributeName': 'vendor_id',
                        'AttributeType': 'S'
                    },
                    {
                        'AttributeName': 'campaign_code',
                        'AttributeType': 'S'
                    }
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'vendor_id-timestamp-index',
                        'KeySchema': [
                            {
                                'AttributeName': 'vendor_id',
                                'KeyType': 'HASH'
                            },
                            {
                                'AttributeName': 'timestamp',
                                'KeyType': 'RANGE'
                            }
                        ],
                        'Projection': {
                            'ProjectionType': 'ALL'
                        },
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    },
                    {
                        'IndexName': 'campaign_code-timestamp-index',
                        'KeySchema': [
                            {
                                'AttributeName': 'campaign_code',
                                'KeyType': 'HASH'
                            },
                            {
                                'AttributeName': 'timestamp',
                                'KeyType': 'RANGE'
                            }
                        ],
                        'Projection': {
                            'ProjectionType': 'ALL'
                        },
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            
            # Wait for table to be created
            table.meta.client.get_waiter('table_exists').wait(
                TableName=settings.DYNAMODB_TABLE_NAME
            )
            
            logger.info(f"Created table {settings.DYNAMODB_TABLE_NAME}")
            return True
            
        except ClientError as e:
            logger.error(f"Error creating table: {e}")
            raise
    
    def delete_table(self) -> bool:
        """
        Delete the audit log table (for testing purposes only).
        
        Returns:
            bool: True if table was deleted, False if it didn't exist
        """
        if not self.table_exists():
            logger.info(f"Table {settings.DYNAMODB_TABLE_NAME} does not exist")
            return False
        
        try:
            self.table.delete()
            
            # Wait for table to be deleted
            self.client.get_waiter('table_not_exists').wait(
                TableName=settings.DYNAMODB_TABLE_NAME
            )
            
            logger.info(f"Deleted table {settings.DYNAMODB_TABLE_NAME}")
            return True
            
        except ClientError as e:
            logger.error(f"Error deleting table: {e}")
            raise


# Global DynamoDB client instance
dynamodb_client = DynamoDBClient()
