FROM cccs/assemblyline-v4-service-base:latest

ENV SERVICE_PATH pixaxe.pixaxe.Pixaxe

USER root

# Get required apt packages
# Image/Science libraries for Python & Tesseract OCR engine/ Language plug-ins
RUN apt-get update && apt-get install -y make perl libjpeg-dev imagemagick wget tar tesseract-ocr tesseract-ocr-all && rm -rf /var/lib/apt/lists/*
RUN pip install Pillow numpy scipy matplotlib

RUN mkdir -p /opt/al_support

# Switch to assemblyline user
USER assemblyline

# Copy Pixaxe service code
WORKDIR /opt/al_service
COPY . .

# Patch version in manifest
ARG version=4.0.0.dev1
USER root
RUN sed -i -e "s/\$SERVICE_TAG/$version/g" service_manifest.yml

# Switch to assemblyline user
USER assemblyline