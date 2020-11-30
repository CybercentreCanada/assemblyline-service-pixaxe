# Pixaxe Service

This Assemblyline service provides metadata extract of various file types and 
image analysis.

**NOTE**: This service does not require you to buy any licence and is
preinstalled and working after a default installation

File types currently supported:

- audiovisual/*
- image/*


# Applications

## PIL library

Python library

AL Outputs:

- Basic image information

## Tesseract

This program is a Optical Character Recognition (OCR) engine, which attempts to extract text from images

Tesseract is licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)

Source code is found here: https://github.com/tesseract-ocr/tesseract

AL outputs:

- Text extracted and appended to file "output.txt"


# Stenography Modules

*Please note that modules are optional (see service configuration). They are provided for academic purposes, 
and are not considered ready for production environments*

Current AL modules:

Least signifcant bit (LSB) analysis:

- Visual attack

- Chi square 

- LSB averages (idea from: http://guillermito2.net/stegano/tools/)

- Couples analysis (python code created largely from java code found here: https://github.com/b3dk7/StegExpose/blob/master/SamplePairs.java)


