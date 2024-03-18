# Pixaxe Service

This Assemblyline service provides image analysis.

**NOTE**: This service does not require you to buy any licence and is
preinstalled and working after a default installation

File types currently supported:

- image/*


# Applications

## Tesseract

This program is a Optical Character Recognition (OCR) engine, which attempts to extract text from images

Tesseract is licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)

Source code is found here: https://github.com/tesseract-ocr/tesseract

AL outputs:

- Text extracted and appended to file "output.txt"

## OCR Configuration
In this service, you're allowed to override the default OCR terms from the [service base](https://github.com/CybercentreCanada/assemblyline-v4-service/blob/master/assemblyline_v4_service/common/ocr.py) using `ocr` key in the `config` block of the service manifest.

### Simple Term Override (Legacy)
Let's say, I want to use a custom set of terms for `ransomware` detection. Then I can set the following:

```yaml
config:
    ocr:
        ransomware: ['bad1', 'bad2', ...]
```

This will cause the service to **only** use the terms I've specified when looking for `ransomware` terms. This is still subject to the hit threshold defined in the service base.

### Advanced Term Override
Let's say, I want to use a custom set of terms for `ransomware` detection and I want to set the hit threshold to `1` instead of `2` (default). Then I can set the following:

```yaml
config:
    ocr:
        ransomware:
            terms: ['bad1', 'bad2', ...]
            threshold: 1
```

This will cause the service to **only** use the terms I've specified when looking for `ransomware` terms and is subject to the hit threshold I've defined.

### Term Inclusion/Exclusion
Let's say, I want to add/remove a set of terms from the default set for `ransomware` detection. Then I can set the following:

```yaml
config:
    ocr:
        ransomware:
            include: ['bad1', 'bad2', ...]
            exclude: ['bank account']
```

This will cause the service to add the terms listed in `include` and remove the terms in `exclude` when looking for `ransomware` terms in OCR detection with the default set.


# Stenography Modules

*Please note that modules are optional (see service configuration). They are provided for academic purposes,
and are not considered ready for production environments*

Current AL modules:

Least significant bit (LSB) analysis:

- Visual attack

- Chi square

- LSB averages (idea from: http://guillermito2.net/stegano/tools/)

- Couples analysis (python code created largely from java code found here: https://github.com/b3dk7/StegExpose/blob/master/SamplePairs.java)
