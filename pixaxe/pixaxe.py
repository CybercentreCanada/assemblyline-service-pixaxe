import hashlib
import os
import re
import struct
import subprocess
from tempfile import NamedTemporaryFile

import magic
from assemblyline.odm.base import FULL_URI
from assemblyline.common.str_utils import safe_str
from assemblyline_v4_service.common.base import ServiceBase
from assemblyline_v4_service.common.result import (
    Result,
    ResultImageSection,
    ResultKeyValueSection,
    ResultMemoryDumpSection,
)
from cairosvg import svg2png
from PIL import Image as PILImage
from PIL import ImageFile, UnidentifiedImageError
from pyzbar.pyzbar import decode as qr_decode
from stegano import lsb
from wand.image import Image

from .steg import ImageInfo, NotSupported

ImageFile.LOAD_TRUNCATED_IMAGES = True


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
        for _, tinfo in iter(self.PAT_FILEMARKERS.items()):

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

    def _analyseGifImage(self, path):
        '''
        Pre-process pass over the image to determine the mode (full or additive).
        Necessary as assessing single frames isn't reliable. Need to know the mode
        before processing all frames.
        '''
        im = PILImage.open(path)
        results = {
            'size': im.size,
            'mode': 'full',
        }
        try:
            while True:
                if im.tile:
                    tile = im.tile[0]
                    update_region = tile[1]
                    update_region_dimensions = update_region[2:]
                    if update_region_dimensions != im.size:
                        results['mode'] = 'partial'
                        break
                im.seek(im.tell() + 1)
        except EOFError:
            pass
        return results

    def _writeGifFrames(self, request, image_preview, ocr_heuristic_id, _handle_ocr_output):
        '''
        Iterate the GIF, extracting each frame.
        '''
        mode = self._analyseGifImage(request.file_path)['mode']

        im = PILImage.open(request.file_path)

        i = 0
        p = im.getpalette()
        last_frame = im.convert('RGBA')

        try:
            while True:
                '''
                If the GIF uses local colour tables, each frame will have its own palette.
                If not, we need to apply the global palette to the new frame.
                '''
                if p is not None and not im.getpalette() and im.mode in ("L", "LA", "P", "PA"):
                    im.putpalette(p)

                new_frame = PILImage.new('RGBA', im.size)

                '''
                Is this file a "partial"-mode GIF where frames update a region of a different size to the entire image?
                If so, we need to construct the new frame by pasting it on top of the preceding frames.
                '''
                if mode == 'partial':
                    new_frame.paste(last_frame)

                new_frame.paste(im, (0, 0), im.convert('RGBA'))
                fh = NamedTemporaryFile(delete=False, suffix='.png')
                new_frame.save(fh.name, 'PNG')
                fh.flush()

                ocr_io = NamedTemporaryFile('w', delete=False)

                image_preview.add_image(fh.name, name=f"{request.file_name}_frame_{i}", description='GIF frame',
                                        ocr_heuristic_id=ocr_heuristic_id, ocr_io=ocr_io)
                _handle_ocr_output(ocr_io, fn_prefix=f"{request.file_name}_frame_{i}")

                i += 1
                last_frame = new_frame
                im.seek(im.tell() + 1)
        except EOFError:
            pass

    def execute(self, request):
        """Main Module. See README for details."""
        result = Result()

        displayable_image_path = request.file_path
        pillow_incompatible = False
        save_ocr_output = request.get_param('save_ocr_output').lower()

        def _handle_ocr_output(ocr_io, fn_prefix):
            # Write OCR output as specified by submissions params
            if save_ocr_output == 'no':
                return
            else:
                # Write content to disk to be uploaded
                if save_ocr_output == 'as_extracted':
                    request.add_extracted(ocr_io.name, f'{fn_prefix}_ocr_output',
                                          description="OCR Output")
                elif save_ocr_output == 'as_supplementary':
                    request.add_supplementary(ocr_io.name, f'{fn_prefix}_ocr_output',
                                              description="OCR Output")
                else:
                    self.log.warning(f'Unknown save method for OCR given: {save_ocr_output}')

        if request.file_type.split('/')[-1] in ['svg', 'wmf', 'emf']:
            try:
                displayable_image_path = os.path.join(self.working_directory, f"{request.file_name}.png")
                if any([request.file_type.endswith(wmf_type) for wmf_type in ['wmf', 'emf']]):
                    # PIL is able to identify WMF but not able to render, therefore we need to convert
                    Image(filename=request.file_path).save(filename=displayable_image_path)
                elif request.file_type.endswith('svg'):
                    # PIL doesn't support SVG so we will need to convert
                    svg2png(bytestring=request.file_contents, write_to=displayable_image_path)

                pillow_incompatible = True
            except Exception:
                # If we can't convert the image for any reason then we can't perform any rendering/OCR
                request.result = Result()
                return

        try:
            # Always provide a preview of the image being analyzed
            image_preview = ResultImageSection(request, "Image Preview")
            ocr_heuristic_id = 1 if not request.file_type == "image/bmp" else None
            if request.file_type == "image/gif":
                # Render all frames in the GIF and append to results
                self._writeGifFrames(request, image_preview, ocr_heuristic_id, _handle_ocr_output)

            else:
                ocr_io = NamedTemporaryFile('w', delete=False)
                image_preview.add_image(displayable_image_path, name=request.file_name, description='Input file',
                                        ocr_heuristic_id=ocr_heuristic_id, ocr_io=ocr_io)
                _handle_ocr_output(ocr_io, fn_prefix=request.file_name)
            image_preview.promote_as_screenshot()
            result.add_section(image_preview)

            # Attempt QR code decoding
            for i, decoded_qr in enumerate(qr_decode(PILImage.open(displayable_image_path))):
                if re.match(FULL_URI, decoded_qr.data.decode()):
                    # Tag URI
                    image_preview.add_tag('network.static.uri', decoded_qr.data)
                else:
                    # Write data to file
                    fh = NamedTemporaryFile(delete=False, mode="wb")
                    fh.write(decoded_qr.data)
                    fh.close()

                    request.add_extracted(fh.name, name=f"embedded_qr_{i}", description="Decoded QR code content")
        except ValueError:
            pass
        except (PILImage.DecompressionBombError, OSError, UnidentifiedImageError):
            if displayable_image_path == request.file_path:
                pillow_incompatible = True

        steg_section = ResultMemoryDumpSection("Steganographical Analysis")
        # Attempt to extract files from the image
        extract_path = NamedTemporaryFile(delete=False)
        p = subprocess.run(
            ['stegseek', '-a', '-f', request.file_path, '/opt/al_service/rockyou.txt', extract_path.name],
            capture_output=True).stderr

        if b'Extracting to' in p:
            self.log.info('Embedded file extracted from image.')
            extracted_section = ResultKeyValueSection("Secret file was extracted from image", parent=steg_section)
            lines = [x for x in p.decode().splitlines() if "e: " in x]
            orig_name = "steg_extract.txt"
            passphrase = None
            for line in lines:
                if 'filename: "' in line:
                    orig_name = line.split('filename: "')[1][:-2]         # Original filename: "Hello.txt".
                if 'passphrase: "' in line:
                    passphrase = line.split('passphrase: "')[1].strip('"')  # Found passphrase: "pass"

            extracted_section.set_item("original_name", orig_name)
            if passphrase is not None:
                extracted_section.set_item("passphrase", passphrase)
            request.add_extracted(extract_path.name, orig_name, 'File extracted from image',
                                  safelist_interface=self.api_interface)
            extracted_section.set_heuristic(2)

        if pillow_incompatible:
            # We can't proceed with further analysis because the original file is incompatible with Pillow
            request.result = result
            return

        secret_msg = None
        if "RGB" not in PILImage.open(request.file_path).mode:
            # Library expects an image containing RGB channels
            secret_msg = None
        elif not request.file_type.endswith('jpg') or request.deep_scan:
            try:
                secret_msg = lsb.reveal(request.file_path)
            except IndexError:
                # Unable to determine a secret message
                pass
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
                request.add_extracted(file_path, file_name, "Carved content found at end of image.",
                                      safelist_interface=self.api_interface)
                with open(file_path, 'wb') as unibu_file:
                    unibu_file.write(additional_content)

        # Steganography modules
        try:
            img_info = ImageInfo(request.file_path, request, steg_section, self.working_directory, self.log)
            self.log.debug(f'Pixel Count: {img_info.pixel_count}')
            if img_info.pixel_count > 100 and \
                    img_info.pixel_count < self.config.get('max_pixel_count', 100000) or \
                    request.deep_scan:
                img_info.decloak()

            if steg_section.body or steg_section.subsections:
                result.add_section(steg_section)
        except NotSupported:
            pass
        request.result = result
