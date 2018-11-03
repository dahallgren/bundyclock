from setuptools import setup, find_packages


setup(
    name="bundyclock",
    version="0.3.1",
    description='Automatic Bundy Clock',
    author="Dan Hallgren",
    author_email="dan.hallgren@gmail.com",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "bundyclock = bundyclock.bundyclock:main",
        ],
    },
    include_package_data=True,
    package_data={
      'bundyclock': ['service_files/*', 'templates/*'],
    },
)
