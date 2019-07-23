import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pyfunccache",
    version="1.0.0.1",
    author="Victor Williams Stafusa da Silva",
    author_email="victorwssilva@gmail.com",
    description="Simple caching and memoization for python functions.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/victorwss/pyfunccache",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ]
)