# AWS_SAM_CDK.md

This file provides guidance when building AWS serverless infrastructure using SAM (Serverless Application Model) and CDK (Cloud Development Kit).

## Philosophy: Infrastructure as Code

**Treat infrastructure like application code. Follow these principles:**

### Core IaC Philosophy
- **Git is the source of truth** - All infrastructure must be defined in version-controlled files
- **No console clicking** - Never create/modify resources directly in AWS Console for production
- **Reproducible environments** - Any environment should be recreatable from code alone
- **Immutable deployments** - Don't patch running infrastructure; deploy new versions

### When to Use SAM vs CDK

| Criteria | SAM | CDK |
|----------|-----|-----|
| **Best for** | Lambda-centric apps, API Gateway, simple serverless | Complex multi-service architectures |
| **Learning curve** | Lower (YAML templates) | Higher (TypeScript/Python code) |
| **Abstraction level** | High-level serverless focus | Full AWS resource access |
| **Testing** | Limited | Full unit testing of infrastructure |
| **Choose when** | Starting out, simple APIs | Need loops/conditionals, complex logic |

**Recommendation for beginners: Start with SAM.**

## SAM (Serverless Application Model)

### Installation & Setup
```bash
# Install
brew install aws-sam-cli

# Verify
sam --version

# Uses existing AWS CLI credentials
# No separate auth required
```

### Project Initialization
```bash
# Create new SAM project (interactive)
sam init

# Create from quick-start template
sam init --runtime python3.12 --name my-api --app-template hello-world
```

### SAM Project Structure
```
my-sam-app/
├── template.yaml          # Infrastructure definition (THE source of truth)
├── samconfig.toml         # Deployment configuration
├── src/
│   └── handlers/          # Lambda function code
│       ├── get_user.py
│       ├── create_order.py
│       └── requirements.txt
├── tests/                 # Unit and integration tests
└── events/                # Sample event payloads for testing
```

### template.yaml Essentials

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: My Serverless API

# Global settings apply to all functions
Globals:
  Function:
    Timeout: 30
    Runtime: python3.12
    MemorySize: 256
    Environment:
      Variables:
        LOG_LEVEL: INFO

Resources:
  # API Gateway
  ApiGateway:
    Type: AWS::Serverless::Api
    Properties:
      StageName: prod
      Cors:
        AllowOrigin: "'*'"
        AllowHeaders: "'Content-Type,Authorization'"
        AllowMethods: "'GET,POST,PUT,DELETE,OPTIONS'"

  # Lambda Function
  GetUserFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/handlers/
      Handler: get_user.lambda_handler
      Events:
        GetUser:
          Type: Api
          Properties:
            RestApiId: !Ref ApiGateway
            Path: /user/{userId}
            Method: GET
      Policies:
        - DynamoDBReadPolicy:
            TableName: !Ref UsersTable

  # DynamoDB Table
  # NOTE: Using Provisioned mode to stay in Free Tier (25 RCU/WCU free)
  # Switch to PAY_PER_REQUEST for production with unpredictable traffic
  UsersTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: users
      BillingMode: PROVISIONED
      ProvisionedThroughput:
        ReadCapacityUnits: 5
        WriteCapacityUnits: 5
      AttributeDefinitions:
        - AttributeName: user_id
          AttributeType: S
      KeySchema:
        - AttributeName: user_id
          KeyType: HASH

Outputs:
  ApiUrl:
    Description: API Gateway endpoint URL
    Value: !Sub "https://${ApiGateway}.execute-api.${AWS::Region}.amazonaws.com/prod/"
```

### SAM Commands Cheat Sheet

```bash
# Build (packages Lambda functions)
sam build

# Local testing
sam local invoke GetUserFunction --event events/get_user.json
sam local start-api  # Runs API locally on http://localhost:3000

# Deploy (first time - interactive)
sam deploy --guided

# Deploy (subsequent - uses saved config)
sam deploy

# View deployed stack outputs
sam list stack-outputs --stack-name my-stack

# Delete stack
sam delete --stack-name my-stack

# Validate template syntax
sam validate

# Sync (hot-reload during development)
sam sync --watch
```

### SAM Best Practices

#### Function Organization
```yaml
# GOOD: Separate functions per endpoint
GetUserFunction:
  Handler: handlers/users.get_handler
CreateUserFunction:
  Handler: handlers/users.create_handler

# BAD: One mega-function routing internally
ApiFunction:
  Handler: handlers/router.main  # Avoid this pattern
```

#### Environment Variables
```yaml
# GOOD: Reference other resources
Environment:
  Variables:
    TABLE_NAME: !Ref UsersTable    # Dynamic reference
    QUEUE_URL: !GetAtt Queue.QueueUrl

# BAD: Hardcoded values
Environment:
  Variables:
    TABLE_NAME: "users-table-prod"  # Never hardcode
```

#### IAM Policies
```yaml
# GOOD: Use SAM policy templates (least privilege)
Policies:
  - DynamoDBCrudPolicy:
      TableName: !Ref UsersTable
  - SQSSendMessagePolicy:
      QueueName: !GetAtt Queue.QueueName

# BAD: Overly permissive
Policies:
  - arn:aws:iam::aws:policy/AdministratorAccess  # NEVER do this
```

## CDK (Cloud Development Kit)

### Installation & Setup
```bash
# Install
npm install -g aws-cdk

# Verify
cdk --version

# Bootstrap (one-time per account/region)
cdk bootstrap aws://ACCOUNT-ID/REGION
```

### Project Initialization
```bash
# Create new CDK project
mkdir my-cdk-app && cd my-cdk-app
cdk init app --language typescript

# Or Python
cdk init app --language python
```

### CDK Project Structure
```
my-cdk-app/
├── bin/
│   └── my-cdk-app.ts      # App entry point
├── lib/
│   └── my-cdk-app-stack.ts # Stack definition
├── lambda/                 # Lambda function code
│   └── handlers/
├── test/                   # Infrastructure tests
├── cdk.json               # CDK configuration
├── package.json
└── tsconfig.json
```

### CDK Stack Example (TypeScript)

```typescript
import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';

export class MyApiStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // DynamoDB Table
    // NOTE: Using Provisioned mode to stay in Free Tier (25 RCU/WCU free)
    // Switch to PAY_PER_REQUEST for production with unpredictable traffic
    const usersTable = new dynamodb.Table(this, 'UsersTable', {
      tableName: 'users',
      partitionKey: { name: 'user_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PROVISIONED,
      readCapacity: 5,
      writeCapacity: 5,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // Lambda Function
    const getUserFn = new lambda.Function(this, 'GetUserFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'get_user.lambda_handler',
      code: lambda.Code.fromAsset('lambda/handlers'),
      environment: {
        TABLE_NAME: usersTable.tableName,
        LOG_LEVEL: 'INFO',
      },
      timeout: cdk.Duration.seconds(30),
    });

    // Grant permissions (CDK handles IAM automatically)
    usersTable.grantReadData(getUserFn);

    // API Gateway
    const api = new apigateway.RestApi(this, 'MyApi', {
      restApiName: 'My Service',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
      },
    });

    const users = api.root.addResource('user');
    const user = users.addResource('{userId}');
    user.addMethod('GET', new apigateway.LambdaIntegration(getUserFn));

    // Output the API URL
    new cdk.CfnOutput(this, 'ApiUrl', {
      value: api.url,
    });
  }
}
```

### CDK Commands Cheat Sheet

```bash
# Synthesize CloudFormation template
cdk synth

# Compare deployed stack with local
cdk diff

# Deploy
cdk deploy

# Deploy all stacks
cdk deploy --all

# Deploy with auto-approval (for CI/CD)
cdk deploy --require-approval never

# Destroy stack
cdk destroy

# List all stacks
cdk list
```

### CDK Best Practices

#### Use Constructs for Reusability
```typescript
// GOOD: Create reusable constructs
export class SecureLambda extends Construct {
  public readonly function: lambda.Function;

  constructor(scope: Construct, id: string, props: SecureLambdaProps) {
    super(scope, id);
    
    this.function = new lambda.Function(this, 'Function', {
      ...props,
      tracing: lambda.Tracing.ACTIVE,  // Always enable X-Ray
      insightsVersion: lambda.LambdaInsightsVersion.VERSION_1_0_119_0,
    });
  }
}

// Usage
const myFn = new SecureLambda(this, 'MyFunction', { ... });
```

#### Environment-Specific Configuration
```typescript
// GOOD: Use context or environment variables
const stage = this.node.tryGetContext('stage') || 'dev';
const config = {
  dev: { memorySize: 256, tableName: 'users-dev' },
  prod: { memorySize: 1024, tableName: 'users-prod' },
}[stage];

// Deploy with: cdk deploy -c stage=prod
```

#### Testing Infrastructure
```typescript
// test/my-stack.test.ts
import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { MyApiStack } from '../lib/my-api-stack';

test('DynamoDB Table Created', () => {
  const app = new cdk.App();
  const stack = new MyApiStack(app, 'TestStack');
  const template = Template.fromStack(stack);

  template.hasResourceProperties('AWS::DynamoDB::Table', {
    BillingMode: 'PAY_PER_REQUEST',
  });
});

test('Lambda Has Correct Environment', () => {
  const app = new cdk.App();
  const stack = new MyApiStack(app, 'TestStack');
  const template = Template.fromStack(stack);

  template.hasResourceProperties('AWS::Lambda::Function', {
    Environment: {
      Variables: {
        LOG_LEVEL: 'INFO',
      },
    },
  });
});

// Run tests: npm test
```

## Deployment Workflow

### Development Workflow
```bash
# 1. Make changes to template.yaml or CDK code
# 2. Validate/synthesize
sam validate        # SAM
cdk synth           # CDK

# 3. Test locally (SAM only)
sam local invoke FunctionName --event event.json

# 4. Deploy to dev
sam deploy --config-env dev
cdk deploy -c stage=dev

# 5. Verify in AWS Console or via CLI
aws lambda invoke --function-name MyFunction output.json

# 6. Commit to git
git add . && git commit -m "Add new endpoint"
```

### CI/CD Pipeline Pattern
```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      # SAM
      - run: sam build && sam deploy --no-confirm-changeset
      
      # OR CDK
      - run: npm ci && npx cdk deploy --require-approval never
```

## Common Patterns

### API + Lambda + DynamoDB (The Holy Trinity)
This is the most common serverless pattern. Both SAM and CDK handle it well.

### Event-Driven Processing
```yaml
# SAM: SQS trigger
Events:
  SQSEvent:
    Type: SQS
    Properties:
      Queue: !GetAtt MyQueue.Arn
      BatchSize: 10
```

```typescript
// CDK: SQS trigger
import * as eventsources from 'aws-cdk-lib/aws-lambda-event-sources';

myFunction.addEventSource(new eventsources.SqsEventSource(queue, {
  batchSize: 10,
}));
```

### Scheduled Tasks (Cron)
```yaml
# SAM
Events:
  ScheduledEvent:
    Type: Schedule
    Properties:
      Schedule: rate(1 hour)
```

```typescript
// CDK
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';

new events.Rule(this, 'HourlyRule', {
  schedule: events.Schedule.rate(cdk.Duration.hours(1)),
  targets: [new targets.LambdaFunction(myFunction)],
});
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `No changes to deploy` | Your code hasn't changed. Force with `--force-upload` (SAM) |
| `Resource already exists` | Resource was created outside IaC. Import or delete manually |
| `Circular dependency` | Refactor to remove circular references between resources |
| `Rate exceeded` | Add retry logic or request limit increase |
| `Template too large` | Split into nested stacks or use asset bucket |

### Debugging Deployed Functions
```bash
# View logs
sam logs -n FunctionName --tail
aws logs tail /aws/lambda/FunctionName --follow

# Invoke and see response
aws lambda invoke --function-name FunctionName output.json && cat output.json
```

## Migration: Existing AWS Resources to IaC

If you have resources already in AWS (like your CAN project), here's how to bring them under IaC control:

### Option 1: Import Existing Resources (Recommended for beginners)
```bash
# SAM/CloudFormation import
# 1. Add resource to template with exact current configuration
# 2. Run import
aws cloudformation import-resources --stack-name my-stack ...
```

### Option 2: Recreate with IaC
1. Export current configurations (like we did with the CAN backup)
2. Write SAM/CDK template matching current state
3. Deploy to new stack
4. Migrate traffic
5. Delete old resources

### Option 3: Gradual Migration
1. Keep existing resources running
2. Add new resources via IaC
3. Slowly migrate functionality
4. Delete legacy resources when empty

## Quick Reference Card

### SAM
```bash
sam init                    # New project
sam build                   # Package functions
sam local invoke            # Test locally
sam local start-api         # Local API server
sam deploy --guided         # First deploy
sam deploy                  # Subsequent deploys
sam delete                  # Destroy stack
```

### CDK
```bash
cdk init app --language typescript  # New project
cdk synth                   # Generate CloudFormation
cdk diff                    # Compare with deployed
cdk deploy                  # Deploy
cdk destroy                 # Destroy stack
npm test                    # Run infrastructure tests
```

## Checklist: Before Deploying to Production

- [ ] All resources defined in IaC (no manual console resources)
- [ ] IAM follows least privilege (no `*` permissions)
- [ ] Environment variables reference resources, not hardcoded values
- [ ] Logging enabled on all Lambda functions
- [ ] Error handling in Lambda code
- [ ] Template validated (`sam validate` / `cdk synth`)
- [ ] Changes committed to git
- [ ] Outputs defined for important resource identifiers
- [ ] Removal policies set appropriately (RETAIN for databases)
