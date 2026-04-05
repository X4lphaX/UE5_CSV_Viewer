"""Build the native C++ acceleration module."""

from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

ext_modules = [
    Pybind11Extension(
        "_native_core",
        ["native/core.cpp"],
        cxx_std=17,
        define_macros=[("NDEBUG", "1")],
    ),
]

setup(
    name="ue5_csv_viewer_native",
    version="1.0.0",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
)
