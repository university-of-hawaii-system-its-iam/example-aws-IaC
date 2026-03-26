#!/usr/bin/env python3
"""CDK application entry point.

Creates the infrastructure stacks in dependency order.
"""
import os
import aws_cdk as cdk

from stacks.network_stack import NetworkStack
from stacks.data_stack import DataStack
from stacks.app_stack import AppStack
from stacks.log_archival_stack import LogArchivalStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION"),
)

# Create the stacks in dependency order
NetworkStack(app, "NetworkStack", env=env)
DataStack(app, "DataStack", env=env)
AppStack(app, "AppStack", env=env)
LogArchivalStack(app, "LogArchivalStack", env=env)

app.synth()

