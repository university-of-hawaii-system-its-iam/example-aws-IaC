"""AppStack - Defines the application infrastructure.

This stack creates:
- ECS Cluster
- ECS Services for API and UI
- Load Balancers
- Auto-scaling configuration
"""
import aws_cdk as cdk
from constructs import Construct


class AppStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # TODO: Add ECS and application resources here

