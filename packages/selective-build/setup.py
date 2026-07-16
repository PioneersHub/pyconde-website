from setuptools import setup

setup(
    name="lektor-selective-build",
    version="0.1.0",
    author="PyConDE Team",
    description="Scope Lektor builds via BUILD_MODE: current | archive | full",
    py_modules=["lektor_selective_build"],
    install_requires=["pyyaml>=6.0"],
    entry_points={
        "lektor.plugins": [
            "selective-build = lektor_selective_build:SelectiveBuildPlugin",
        ]
    },
)
