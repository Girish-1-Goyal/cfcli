from setuptools import setup

setup(
    name="cfcli",
    version="0.1.0",
    description="Codeforces Command Line Interface",
    author="Codeforces CLI",
    py_modules=["cfcli"],
    install_requires=[
        "click",
        "colorama",
        "python-dotenv",
        "requests",
    ],
    entry_points={
        "console_scripts": [
            "cfcli=cfcli:cli",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Topic :: Utilities",
    ],
    python_requires=">=3.6",
) 