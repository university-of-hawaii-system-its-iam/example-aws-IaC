"""DataStack - Defines the data infrastructure.

This stack creates:
- RDS/Aurora database
- ElastiCache for caching
- S3 buckets for storage
- Secrets for database credentials
"""
import aws_cdk as cdk
from constructs import Construct


class DataStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # TODO: Add data resources here

