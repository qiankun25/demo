from setuptools import setup, find_packages

setup(
    name="nexus-sdk",
    version="0.1.0",
    author="Nexus Team",
    description="Standard SDK for Nexus Tool Services",
    packages=find_packages(),
    install_requires=[
        "aio-pika>=9.0.0",
        "pydantic>=2.0.0"
    ],
    python_requires=">=3.8",
)
