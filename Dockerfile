ARG branch=latest
FROM cccs/assemblyline-v4-service-base:$branch

ENV SERVICE_PATH pixaxe.pixaxe.Pixaxe
ENV TESSERACT_VERSION 5.3.0

USER root

# Get required apt packages
# Image/Science libraries for Python & Tesseract OCR engine/ Language plug-ins
RUN apt-get update && apt-get install -y wget libjpeg-dev zlib1g-dev imagemagick libmagickwand-dev libgl1

# Install Tesseract from source
RUN apt-get install -y g++ autoconf automake libtool pkg-config libpng-dev libtiff5-dev zlib1g-dev libleptonica-dev libpango1.0-dev build-essential
RUN wget https://github.com/tesseract-ocr/tesseract/archive/refs/tags/${TESSERACT_VERSION}.tar.gz
RUN tar -xvf ${TESSERACT_VERSION}.tar.gz
WORKDIR tesseract-${TESSERACT_VERSION}
RUN ./autogen.sh && ./configure --disable-dependency-tracking && make && make install && ldconfig
RUN wget https://raw.githubusercontent.com/tesseract-ocr/tessdata/main/eng.traineddata -O /usr/local/share/tessdata/eng.traineddata

RUN pip install Pillow numpy scipy matplotlib pytesseract stegano wand cairosvg

# Used for decoding QR codes
RUN apt-get install -y libzbar0 && pip install pyzbar

RUN mkdir -p /opt/al_support

# Install Steganalysis library
RUN wget https://github.com/RickdeJager/stegseek/releases/download/v0.6/stegseek_0.6-1.deb
RUN apt-get install -y ./stegseek_0.6-1.deb && rm -f ./stegseek_0.6-1.deb  && rm -rf /var/lib/apt/lists/*
RUN wget https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt -O /opt/al_service/rockyou.txt

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
