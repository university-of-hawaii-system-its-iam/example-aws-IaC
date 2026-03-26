import setuptools

setuptools.setup(
    name="example-aws-iac",
    version="1.0.0",
    description="AWS Infrastructure as Code project for containerized application on ECS",
    author="UH Groupings Infrastructure Team",
    packages=setuptools.find_packages(),
    install_requires=[
        "aws-cdk-lib>=2.100.0",
        "constructs>=10.0.0",
    ],
    python_requires=">=3.9",
)

