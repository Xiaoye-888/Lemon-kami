from setuptools import setup, find_packages
from pathlib import Path

# 读取 README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="lemon-kami-sdk",
    version="1.0.0",
    author="Lemon Kami",
    author_email="support@example.com",
    description="小柠檬网络验证 Python SDK - 提供卡密验证、事件上报、设备绑定等功能",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/lemon-kami",
    py_modules=["lemon_kami"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "requests>=2.31.0",
        "pycryptodome>=3.19.0",
    ],
    keywords="kami license authentication sdk lemon",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/lemon-kami/issues",
        "Source": "https://github.com/yourusername/lemon-kami/sdk/python_sdk",
    },
)
