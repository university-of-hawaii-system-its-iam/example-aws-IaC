#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { NetworkStack } from "../lib/network-stack";
import { AppStack } from "../lib/app-stack";
import { DataStack } from "../lib/data-stack";

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION,
};

// Create the stacks in dependency order
new NetworkStack(app, "NetworkStack", { env });
new DataStack(app, "DataStack", { env });
new AppStack(app, "AppStack", { env });

