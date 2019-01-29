from distutils.core import setup
from Cython.Build import cythonize

setup(
    ext_modules = cythonize(
        [
            "ps2textures.pyx",
            "imageops.pyx",
        ],
        annotate=True)
)