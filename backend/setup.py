"""Setup file for HSA Tracker backend package"""

from setuptools import setup, find_packages

setup(
    name="hsa-tracker",
    version="0.1.0",
    description="Self-hosted HSA expense tracking application",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "sqlalchemy>=2.0.25",
        "alembic>=1.13.1",
        "pydantic>=2.5.3",
        "pydantic-settings>=2.1.0",
        "boto3>=1.34.34",
    ],
)
