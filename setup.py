from setuptools import setup, find_packages

exec(open('morphoblend/__version__.py').read())
setup(
    name='morphoblend',
    version=__version__,
    packages=find_packages(exclude=["tests"]),
    include_package_data=True,
    description='Addon for visualisation, processing and quantification of cell segmentation',
    author='Alexis Maizel',
    url='https://github.com/AlexisMaizel/MorphoBlend',
    author_email='alexis.maizel@cos.uni-heidelberg.de',
)