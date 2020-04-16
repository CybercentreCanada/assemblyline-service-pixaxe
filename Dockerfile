FROM cccs/assemblyline-v4-service-base:latest

ENV SERVICE_PATH pixaxe.pixaxe.Pixaxe

USER root

# Get required apt packages

# Image/Science libraries for Python
RUN apt-get update && apt-get install -y libjpeg-dev python-numpy python-scipy python-matplotlib imagemagick wget unzip && rm -rf /var/lib/apt/lists/*
RUN pip install Pillow
# Tesseract OCR engine/ Language plug-ins
RUN apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-all && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/al_support

# Download the support files from Amazon S3
RUN wget -O /tmp/exiftool.tar.gz https://exiftool.org/Image-ExifTool-11.93.tar.gz
RUN unzip -o /tmp/exiftool.tar.gz -d /opt/al_support/exiftool

# Cleanup
RUN rm -rf /tmp/*

# Switch to assemblyline user
USER assemblyline

# Copy Pixaxe service code
WORKDIR /opt/al_service
COPY . .