import setuptools

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

def read_requirements():
    with open("requirements.txt", "r") as f:
        return f.read().splitlines()

setuptools.setup(
    name='swesynth',
    author='thaiminhpv',
    author_email='thaiminhpv@gmail.com',
    description='',
    keywords='',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3 :: Only',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.10',
    install_requires=read_requirements(),
    extras_require={
        'cosmic_ray': [
            'cosmic-ray==8.4.*'
        ]
    },
    include_package_data=True,
)