ARG branch=latest
FROM cccs/assemblyline-v4-service-base:$branch

ENV SERVICE_PATH pixaxe.pixaxe.Pixaxe

USER root

# Get required apt packages
# Image/Science libraries for Python & Tesseract OCR engine/ Language plug-ins
RUN apt-get update && apt-get install -y wget libjpeg-dev zlib1g-dev imagemagick tesseract-ocr tesseract-ocr-all
RUN pip install Pillow numpy scipy matplotlib pytesseract stegano

RUN mkdir -p /opt/al_support

# Install Steganalysis library
RUN wget https://github.com/RickdeJager/stegseek/releases/download/v0.6/stegseek_0.6-1.deb
RUN apt-get install -y ./stegseek_0.6-1.deb && rm -f ./stegseek_0.6-1.deb  && rm -rf /var/lib/apt/lists/*
RUN wget -o /opt/al_service/rockyou.txt https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt

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
