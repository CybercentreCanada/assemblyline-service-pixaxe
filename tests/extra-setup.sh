# Install Steganalysis library from source
mkdir -p /opt/al_service/
wget https://github.com/RickdeJager/stegseek/releases/download/v0.6/stegseek_0.6-1.deb
apt-get install -y ./stegseek_0.6-1.deb && rm -f ./stegseek_0.6-1.deb
wget https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt -O /opt/al_service/rockyou.txt
