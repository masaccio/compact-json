from setuptools import setup, find_packages

main_ns = {}
with open("src/compact_json/_version.py") as ver_file:
    exec(ver_file.read(), main_ns)


setup(
    name="compact-json",
    version=main_ns["__version__"],
    author="Jon Connell",
    author_email="python@figsandfudge.com",
    description="A JSON formatter that produces compact but human-readable",
    license="MIT",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/masaccio/compact-json",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={
        "console_scripts": [
            "compact-json=compact_json._compact_json:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
