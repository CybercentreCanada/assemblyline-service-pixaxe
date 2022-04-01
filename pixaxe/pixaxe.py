import hashlib
import magic
import os
import re
import struct
import subprocess

from stegano import lsb
from tempfile import NamedTemporaryFile
from .steg import ImageInfo, NotSupported
from wand.image import Image
from PIL import Image as PILImage

from assemblyline.common.str_utils import safe_str
from assemblyline_v4_service.common.base import ServiceBase
from assemblyline_v4_service.common.result import Result, ResultImageSection, ResultMemoryDumpSection, ResultTextSection


class Pixaxe(ServiceBase):
    PAT_FILEMARKERS = {
        # Header, Trailer, additional methods
        'bmp': ['\x42\x4D', None, 'bmp_dump'],
        'gif': ['\x47\x49\x46\x38.\x61.{19,}\x2C.{9,}', '\x00\x3B', None],
        'jpeg': ['\xFF\xD8.{18}\xFF\xDB.{3,}\xFF\xDA.{13,}', '\xFF\xD9', None],
        'jpeg2000': ['\x00\x00\x00\x0C\x6A\x50\x20\x20\x0D\x0A', None, 'jp2_dump'],
        'png': ['\x89\x50\x4E\x47', '\x49\x45\x4E\x44.{4}', None],
    }

    def __init__(self, config=None):
        super(Pixaxe, self).__init__(config)

    def start(self):
        self.log.debug("Pixaxe service started")

    @staticmethod
    def mimetype(f, t):
        """Determine if Magic-MIME file type of data matches desired file type.

        Args:
            f: Raw data to evaluate.
            t: File type to compare (string).

        Returns:
            True if file type matches t, or False.
        """
        is_t = False
        m = magic.Magic(mime=True)
        ftype = m.from_buffer(f)
        if t in ftype:
            is_t = True
        return is_t

    def bmp_dump(self, data):
        """BMP embedded file extraction. Looks for traits of known BMP file structure to find embedded BMP data.

        Args:
            data: Raw data to search.

        Returns:
            BMP data if discovered, or original data.
        """
        # noinspection PyBroadException
        try:
            # Byte offset to start of image
            soi = struct.unpack('<I', data[10:14])[0]
            # Size of image data, including padding -- potentially unreliable
            sizei = struct.unpack('<I', data[34:38])[0]
            # Width in pixels
            # wi = struct.unpack('<I', data[18:22])[0]
            # Height in pixels
            # hi = struct.unpack('<I', data[22:26])[0]
            # Depth
            # di = struct.unpack('<H', data[26:28])[0]
            # Bits per pixel
            # bpi = struct.unpack('<H', data[28:30])[0]
            # Image bytes
            # sizei = (wi*hi*di*bpi)/8
            bmp_data = data[0:(soi + sizei)]
            verify_bmp = self.mimetype(bmp_data, 'image')
            if not verify_bmp:
                return data
            return bmp_data
        except Exception:
            return data

    def jpg2_dump(self, data):
        """Looks for traits of known JPEG 2000 file structure to confirm that data is likely JPEG 2000 data.

        Args:
            data: Raw data to search.

        Returns:
            JPEG 2000 data if discovered, or original data.
        """
        ftyps = {
            '\x6a\x70\x32\x20': 'jp2',
            '\x6a\x70\x78\x20': 'jpf',
            '\x6a\x70\x6d\x20': 'jpm',
            '\x6d\x6a\x70\x32': 'mj2',
            '\xFF\x4F\xFF\x51': 'j2c'
        }
        trailer = '\xFF\xD9'
        cdata = data
        end = 0
        try:
            jtype = data[20:24]
            if jtype in ftyps:
                file_type = ftyps[jtype]
                self.log.debug(file_type)
            else:
                return
            while True:
                findend = cdata.find(trailer)
                if findend == -1:
                    return
                else:
                    end += findend + 2
                # Another jp2 codestream
                if cdata[findend + 6:findend + 10] == 'jp2c':
                    cdata = cdata[findend + 2:]
                # Possible .mov file types
                elif file_type == 'mj2' and cdata[findend + 6:findend + 10] in \
                        ['free', 'mdat', 'moov', 'pnot', 'skip', 'wide']:
                    msize = struct.unpack('>I', cdata[findend + 2:findend + 6])[0]
                    jp2_data = data[0:end + msize]
                    break
                else:
                    jp2_data = data[0:end]
                    break
            return jp2_data
        except Exception:
            return

    def find_additional_content(self, alfile):
        """Looks for appended file content attached to an image.

        Args:
            alfile: AL submission file path.

        Returns:
            Embedded file data if found, or None.
        """
        with open(alfile, 'rb') as f:
            data = f.read()
        for ftype, tinfo in iter(self.PAT_FILEMARKERS.items()):

            # Build up the regex
            if tinfo[1] is not None:
                embed_regex = re.compile(tinfo[0] + '.+' + tinfo[1], re.DOTALL)
            else:
                embed_regex = re.compile(tinfo[0] + '.+', re.DOTALL)

            # Find the pattern that should match the image.
            img_match = re.match(embed_regex, str(data))
            if img_match:
                img_data = img_match.group()
                # Go to extraction module if there is one
                if tinfo[2] is not None:
                    img_data = getattr(self, tinfo[2])(img_data)

                # Otherwise extract data as-is (regex is considered good enough)
                leftovers = data.replace(img_data, b"")

                # Remove trailing NULL bytes
                leftovers = re.sub(b'[\x00]*$', b'', leftovers)

                if len(leftovers) > 15:
                    return leftovers
        return

    def execute(self, request):
        """Main Module. See README for details."""
        result = Result()

        displayable_image_path = request.file_path
        pillow_incompatible = False
        if request.file_type.endswith('wmf'):
            # PIL is able to identify WMF but not able to render, therefore we need to convert
            displayable_image_path = os.path.join(self.working_directory, f"{request.file_name}.png")
            Image(filename=request.file_path).save(filename=displayable_image_path)
            pillow_incompatible = True

        try:
            # Always provide a preview of the image being analyzed
            image_preview = ResultImageSection(request, "Image Preview")
            image_preview.add_image(displayable_image_path, name=request.file_name, description='Input file',
                                    ocr_heuristic_id=1)
            result.add_section(image_preview)
        except PILImage.DecompressionBombError:
            pillow_incompatible = True
            pass
        except OSError:
            pillow_incompatible = True

        steg_section = ResultTextSection("Steganographical Analysis")
        # Attempt to extract files from the image
        extract_path = NamedTemporaryFile(delete=False)
        p = subprocess.run(
            ['stegseek', '-a', '-f', request.file_path, '/opt/al_service/rockyou.txt', extract_path.name],
            capture_output=True).stderr

        if b'Extracting to' in p:
            self.log.info('Embedded file extracted from image.')
            lines = p.splitlines()
            orig_name = lines[1][20:-2].decode()        # Original filename: "Hello.txt".

            body = f"File was extracted from image: \n{p.decode()}"
            steg_section.set_body(body)
            request.add_extracted(extract_path.name, orig_name, 'File extracted from image')
            steg_section.set_heuristic(2)

        if pillow_incompatible:
            # We can't proceed with further analysis because the original file is incompatible with Pillow
            request.result = result
            return

        secret_msg = None
        if "RGB" not in PILImage.open(request.file_path).mode:
            # Library expects an image containing RGB channels
            secret_msg = None
        elif not request.file_type.endswith('jpg') or request.deep_scan:
            secret_msg = lsb.reveal(request.file_path)
        # Think it's unlikely to have both a hidden message and an embedded file
        if secret_msg:
            self.log.info('Secret message found.')
            steg_section.set_body(f'Secret message found:\n{secret_msg}')
            steg_section.set_heuristic(2)

        # Default to original behaviour
        else:
            # Find attached data
            additional_content = self.find_additional_content(request.file_path)
            if additional_content:
                ares = ResultMemoryDumpSection("Possible Appended Content Found")
                ares.add_line("{} Bytes of content found at end of image file".format(len(additional_content)))
                ares.add_line("Text preview (up to 500 bytes):\n")
                ares.add_line("{}".format(safe_str(additional_content)[0:500]))
                ares.set_heuristic(2)
                result.add_section(ares)
                file_name = "{}_appended_img_content".format(hashlib.sha256(additional_content).hexdigest()[0:10])
                file_path = os.path.join(self.working_directory, file_name)
                request.add_extracted(file_path, file_name, "Carved content found at end of image.")
                with open(file_path, 'wb') as unibu_file:
                    unibu_file.write(additional_content)

        # Steganography modules
        try:
            img_info = ImageInfo(request.file_path, request, steg_section, self.working_directory, self.log)
            self.log.info(f'Pixel Count: {img_info.pixel_count}')
            if img_info.pixel_count < self.config.get('max_pixel_count', 10000000) or request.deep_scan:
                img_info.decloak()

            if steg_section.body or steg_section.subsections:
                result.add_section(steg_section)
        except NotSupported:
            pass
        request.result = result
