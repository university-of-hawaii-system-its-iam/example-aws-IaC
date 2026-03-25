import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

/**
 * LogArchivalStack - Infrastructure for log rotation and long-term archival
 * 
 * This stack provides:
 * - S3 bucket for log archives with lifecycle policies
 * - Lambda function for exporting CloudWatch logs to S3
 * - EventBridge rule for scheduled log exports
 * - IAM roles and permissions
 */
export class LogArchivalStack extends cdk.Stack {
  public readonly logArchiveBucket: s3.Bucket;
  public readonly exportLogsFunction: lambda.Function;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const accountId = cdk.Stack.of(this).account;
    const region = cdk.Stack.of(this).region;

    // ========================================
    // S3 Bucket for Log Archives
    // ========================================
    this.logArchiveBucket = new s3.Bucket(this, 'log-archive-bucket', {
      bucketName: `uh-groupings-logs-archive-${accountId}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: true,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          // Transition to GLACIER after 90 days
          transitions: [
            {
              storageClass: s3.StorageClass.GLACIER,
              transitionAfter: cdk.Duration.days(90),
            },
            // Deep archive after 180 days for cost savings
            {
              storageClass: s3.StorageClass.DEEP_ARCHIVE,
              transitionAfter: cdk.Duration.days(180),
            },
          ],
          // Expire after 7 years (2555 days) for compliance
          expiration: cdk.Duration.days(2555),
          // Delete incomplete multipart uploads after 7 days
          abortIncompleteMultipartUpload: {
            daysAfterInitiation: 7,
          },
        },
      ],
    });

    // ========================================
    // CloudWatch Log Groups for ECS Services
    // ========================================
    const apiLogGroup = new logs.LogGroup(this, 'api-log-group', {
      logGroupName: '/ecs/uh-groupings/api',
      retention: logs.RetentionDays.SEVEN_DAYS,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const uiLogGroup = new logs.LogGroup(this, 'ui-log-group', {
      logGroupName: '/ecs/uh-groupings/ui',
      retention: logs.RetentionDays.SEVEN_DAYS,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // ========================================
    // Lambda Function for Log Export
    // ========================================
    this.exportLogsFunction = new lambda.Function(
      this,
      'export-logs-function',
      {
        runtime: lambda.Runtime.PYTHON_3_11,
        handler: 'index.handler',
        code: lambda.Code.fromInline(`
import boto3
import json
import os
from datetime import datetime, timedelta

logs_client = boto3.client('logs')
s3_bucket = os.environ['LOG_BUCKET']

def handler(event, context):
    log_groups = [
        '/ecs/uh-groupings/api',
        '/ecs/uh-groupings/ui',
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
                destinationPrefix=f"cloudwatch-logs/{log_group}/{datetime.utcnow().strftime('%Y/%m/%d')}"
            )
            results.append({
                'logGroup': log_group,
                'taskId': response['taskId'],
                'status': 'PENDING'
            })
            print(f"Export task created for {log_group}: {response['taskId']}")
        except Exception as e:
            results.append({
                'logGroup': log_group,
                'error': str(e)
            })
            print(f"Error exporting logs for {log_group}: {str(e)}")
    
    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }
`),
        environment: {
          LOG_BUCKET: this.logArchiveBucket.bucketName,
        },
        timeout: cdk.Duration.minutes(5),
        description: 'Exports CloudWatch logs to S3 for long-term archival',
      }
    );

    // Grant S3 permissions to Lambda
    this.logArchiveBucket.grantWrite(this.exportLogsFunction);

    // Grant CloudWatch Logs permissions
    this.exportLogsFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'logs:CreateExportTask',
          'logs:DescribeExportTasks',
        ],
        resources: ['*'],
      })
    );

    // ========================================
    // EventBridge Rule for Scheduled Exports
    // ========================================
    const rule = new events.Rule(this, 'export-logs-schedule', {
      schedule: events.Schedule.cron({
        hour: '2',      // 2 AM UTC
        minute: '0',
        day: '*',
      }),
      description: 'Daily export of CloudWatch logs to S3',
    });

    rule.addTarget(new targets.LambdaTarget(this.exportLogsFunction));

    // ========================================
    // Stack Outputs
    // ========================================
    new cdk.CfnOutput(this, 'LogArchiveBucketName', {
      value: this.logArchiveBucket.bucketName,
      description: 'S3 bucket for log archives',
      exportName: 'uh-groupings-log-archive-bucket',
    });

    new cdk.CfnOutput(this, 'ApiLogGroupName', {
      value: apiLogGroup.logGroupName,
      description: 'CloudWatch log group for API service',
      exportName: 'uh-groupings-api-log-group',
    });

    new cdk.CfnOutput(this, 'UiLogGroupName', {
      value: uiLogGroup.logGroupName,
      description: 'CloudWatch log group for UI service',
      exportName: 'uh-groupings-ui-log-group',
    });
  }
}

