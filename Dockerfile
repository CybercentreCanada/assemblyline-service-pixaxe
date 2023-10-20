ARG branch=latest
FROM cccs/assemblyline-v4-service-base:$branch

ENV SERVICE_PATH pixaxe.pixaxe.Pixaxe
ENV TESSERACT_VERSION 5.3.0

# Switch to root user
USER root

# Install apt dependencies
COPY pkglist.txt pkglist.txt
RUN apt-get update && grep -vE '^#' pkglist.txt | xargs apt-get install -y && rm -rf /var/lib/apt/lists/*

# Install Tesseract from source
RUN wget https://github.com/tesseract-ocr/tesseract/archive/refs/tags/${TESSERACT_VERSION}.tar.gz
RUN tar -xvf ${TESSERACT_VERSION}.tar.gz
WORKDIR tesseract-${TESSERACT_VERSION}
RUN ./autogen.sh && ./configure --disable-dependency-tracking && make && make install && ldconfig
RUN wget https://raw.githubusercontent.com/tesseract-ocr/tessdata/main/eng.traineddata -O /usr/local/share/tessdata/eng.traineddata

# Install python dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --user --requirement requirements.txt && rm -rf ~/.cache/pip

RUN mkdir -p /opt/al_support

# Install Steganalysis library from source
RUN apt-get update
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
