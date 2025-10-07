from setuptools import setup

setup(
    name="lektor-yaml-databags",
    version="0.1.0",
    author="PyConDE Team",
    description="Adds YAML support for Lektor databags",
    py_modules=["lektor_yaml_databags"],
    install_requires=["pyyaml>=6.0"],
    entry_points={
        "lektor.plugins": [
            "yaml-databags = lektor_yaml_databags:YAMLDatabagPlugin",
        ]
    },
)
