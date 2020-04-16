#!/usr/bin/env python
import os


def install(alsi):

    # Image/Science libraries for Python
    alsi.sudo_apt_install('libjpeg-dev')
    alsi.pip_install_all([
        'Pillow',
    ])
    alsi.sudo_apt_install('python-numpy')
    alsi.sudo_apt_install('python-scipy')
    alsi.sudo_apt_install('python-matplotlib')

    # For possible enhancement of image files
    alsi.sudo_apt_install('imagemagick')

    # Exiftool
    wd = os.getcwd()
    exif_support = os.path.join(alsi.alroot, 'support/exiftool')
    local_exif = os.path.join(exif_support, 'Image-ExifTool-11.16.tar.gz')
    alsi.fetch_package('exiftool/Image-ExifTool-11.16.tar.gz', local_exif)
    os.chdir(exif_support)
    alsi.runcmd('tar xvf Image-ExifTool-11.16.tar.gz')
    os.chdir(os.path.join(exif_support, 'Image-ExifTool-11.16/'))
    alsi.runcmd('perl Makefile.PL')
    alsi.runcmd('sudo make install')
    os.chdir(wd)

    # Tesseract OCR engine/ Language plug-ins
    alsi.sudo_apt_install('tesseract-ocr')
    alsi.sudo_apt_install('tesseract-ocr-all')


if __name__ == '__main__':
    from assemblyline.al.install import SiteInstaller
    install(SiteInstaller())
