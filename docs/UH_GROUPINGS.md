

# AWS Secrets Injection

The AWS Secrets Manager injects secrets as environment variables. This allows
Spring Boot to access the secrets without any additional code or configuration
changes. The @Value annotation is used for this.

There is a fixed cost to injecting a secret, so best to limit this to actual
secrets.

## Spring Boot Property Sources Hierarchy

Spring Boot automatically loads properties in the following order of precedence 
(highest to lowest):
* Command-line arguments
* System environment variables
* application.properties (and environment-specific variants)
* External property files specified via spring.config.import
* Default values in the code (if any)

# AWS Parameter Store 

The application must be configured to use the AWS Parameter Store as a property 
source. This is done by adding the following dependency to the project pom.xml 
file:

```xml
<dependency>
  <groupId>io.awspring.cloud</groupId>
  <artifactId>spring-cloud-aws-starter-ssm-parameter-store</artifactId>
  <version>3.1.1</version>
</dependency>
<dependency>
  <groupId>software.amazon.awssdk</groupId>
  <artifactId>ssm</artifactId>
</dependency>
```
Add configuration to application-prod.properties:

```properties
spring.config.import=aws-parameterstore://
spring.cloud.aws.ssm.prefix=/prod/app
```

Once the above are in place, Spring Boot will automatically load properties from
the AWS Parameter Store. The properties can be accessed using the @Value 
annotation. 