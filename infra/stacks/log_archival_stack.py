"""LogArchivalStack - Infrastructure for log rotation and long-term archival.

This stack provides:
- S3 bucket for log archives with lifecycle policies
- Lambda function for exporting CloudWatch logs to S3
- EventBridge rule for scheduled log exports
- IAM roles and permissions
"""
import textwrap

import aws_cdk as cdk
from aws_cdk import (
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_s3 as s3,
)
from constructs import Construct


class LogArchivalStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        account_id = cdk.Stack.of(self).account
        region = cdk.Stack.of(self).region

        # ========================================
        # S3 Bucket for Log Archives
        # ========================================
        self.log_archive_bucket = s3.Bucket(
            self,
            "log-archive-bucket",
            bucket_name=f"uh-groupings-logs-archive-{account_id}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            enforce_ssl=True,
            removal_policy=cdk.RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    transitions=[
                        # Transition to GLACIER after 90 days
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=cdk.Duration.days(90),
                        ),
                        # Deep archive after 180 days for cost savings
                        s3.Transition(
                            storage_class=s3.StorageClass.DEEP_ARCHIVE,
                            transition_after=cdk.Duration.days(180),
                        ),
                    ],
                    # Expire after 7 years (2555 days) for compliance
                    expiration=cdk.Duration.days(2555),
                    # Delete incomplete multipart uploads after 7 days
                    abort_incomplete_multipart_upload_after=cdk.Duration.days(7),
                ),
            ],
        )

        # ========================================
        # CloudWatch Log Groups for ECS Services
        # ========================================
        api_log_group = logs.LogGroup(
            self,
            "api-log-group",
            log_group_name="/ecs/uh-groupings/api",
            retention=logs.RetentionDays.SEVEN_DAYS,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        ui_log_group = logs.LogGroup(
            self,
            "ui-log-group",
            log_group_name="/ecs/uh-groupings/ui",
            retention=logs.RetentionDays.SEVEN_DAYS,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # ========================================
        # Lambda Function for Log Export
        # ========================================
        export_handler_code = textwrap.dedent("""\
            import boto3
            import json
            import os
            from datetime import datetime, timedelta

            logs_client = boto3.client("logs")
            s3_bucket = os.environ["LOG_BUCKET"]

            def handler(event, context):
                log_groups = [
                    "/ecs/uh-groupings/api",
                    "/ecs/uh-groupings/ui",
                ]

                # Export logs from previous day
                end_time = int(datetime.utcnow().timestamp() * 1000)
                start_time = int((datetime.utcnow() - timedelta(days=1)).timestamp() * 1000)

                results = []
                for log_group in log_groups:
                    try:
                        response = logs_client.create_export_task(
                            logGroupName=log_group,
                            fromTime=start_time,
                            to=end_time,
                            destination=s3_bucket,
                            destinationPrefix=f"cloudwatch-logs/{log_group}/{datetime.utcnow().strftime('%Y/%m/%d')}",
                        )
                        results.append({
                            "logGroup": log_group,
                            "taskId": response["taskId"],
                            "status": "PENDING",
                        })
                        print(f"Export task created for {log_group}: {response['taskId']}")
                    except Exception as e:
                        results.append({
                            "logGroup": log_group,
                            "error": str(e),
                        })
                        print(f"Error exporting logs for {log_group}: {e}")

                return {"statusCode": 200, "body": json.dumps(results)}
        """)

        self.export_logs_function = lambda_.Function(
            self,
            "export-logs-function",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline(export_handler_code),
            environment={
                "LOG_BUCKET": self.log_archive_bucket.bucket_name,
            },
            timeout=cdk.Duration.minutes(5),
            description="Exports CloudWatch logs to S3 for long-term archival",
        )

        # Grant S3 permissions to Lambda
        self.log_archive_bucket.grant_write(self.export_logs_function)

        # Grant CloudWatch Logs permissions
        self.export_logs_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateExportTask",
                    "logs:DescribeExportTasks",
                ],
                resources=["*"],
            )
        )

        # ========================================
        # EventBridge Rule for Scheduled Exports
        # ========================================
        rule = events.Rule(
            self,
            "export-logs-schedule",
            schedule=events.Schedule.cron(
                hour="2",  # 2 AM UTC
                minute="0",
                day="*",
            ),
            description="Daily export of CloudWatch logs to S3",
        )

        rule.add_target(targets.LambdaFunction(self.export_logs_function))

        # ========================================
        # Stack Outputs
        # ========================================
        cdk.CfnOutput(
            self,
            "LogArchiveBucketName",
            value=self.log_archive_bucket.bucket_name,
            description="S3 bucket for log archives",
            export_name="uh-groupings-log-archive-bucket",
        )

        cdk.CfnOutput(
            self,
            "ApiLogGroupName",
            value=api_log_group.log_group_name,
            description="CloudWatch log group for API service",
            export_name="uh-groupings-api-log-group",
        )

        cdk.CfnOutput(
            self,
            "UiLogGroupName",
            value=ui_log_group.log_group_name,
            description="CloudWatch log group for UI service",
            export_name="uh-groupings-ui-log-group",
        )

