import hashlib
import os
import re
import subprocess
from tempfile import NamedTemporaryFile
from typing import Optional

from assemblyline.common.str_utils import safe_str
from assemblyline.odm.base import FULL_URI
from assemblyline_v4_service.common.base import ServiceBase
from assemblyline_v4_service.common.request import ServiceRequest
from assemblyline_v4_service.common.result import (
    Heuristic,
    Result,
    ResultImageSection,
    ResultKeyValueSection,
    ResultMemoryDumpSection,
    ResultSection,
)
from cairosvg import svg2png
from multidecoder.decoders.network import find_emails, find_urls
from PIL import Image as PILImage, ImageOps
from PIL import ImageFile, UnidentifiedImageError
from stegano import lsb
from wand.image import Image

from pixaxe.steg import ImageInfo, NotSupported
from pixaxe.helper import find_additional_content

ImageFile.LOAD_TRUNCATED_IMAGES = True


class Pixaxe(ServiceBase):
    def __init__(self, config=None):
        super(Pixaxe, self).__init__(config)

    def start(self):
        self.log.debug("Pixaxe service started")

    def tag_network_iocs(self, section: ResultSection, ocr_io: NamedTemporaryFile) -> None:
        ocr_io.seek(0)
        ocr_content = ocr_io.read()
        [section.add_tag("network.email.address", node.value) for node in find_emails(ocr_content.encode())]
        [section.add_tag("network.static.uri", node.value) for node in find_urls(ocr_content.encode())]

    def _analyseGifImage(self, path):
        """
        Pre-process pass over the image to determine the mode (full or additive).
        Necessary as assessing single frames isn't reliable. Need to know the mode
        before processing all frames.
        """
        im = PILImage.open(path)
        results = {
            "size": im.size,
            "mode": "full",
        }
        try:
            while True:
                if im.tile:
                    tile = im.tile[0]
                    update_region = tile[1]
                    update_region_dimensions = update_region[2:]
                    if update_region_dimensions != im.size:
                        results["mode"] = "partial"
                        break
                im.seek(im.tell() + 1)
        except EOFError:
            pass
        return results

    def _writeGifFrames(self, request, image_preview, ocr_heuristic_id, _handle_ocr_output):
        """
        Iterate the GIF, extracting each frame.
        """
        mode = self._analyseGifImage(request.file_path)["mode"]

        im = PILImage.open(request.file_path)

        i = 0
        p = im.getpalette()
        last_frame = im.convert("RGBA")

        try:
            while True:
                """
                If the GIF uses local colour tables, each frame will have its own palette.
                If not, we need to apply the global palette to the new frame.
                """
                if p is not None and not im.getpalette() and im.mode in ("L", "LA", "P", "PA"):
                    im.putpalette(p)

                new_frame = PILImage.new("RGBA", im.size)

                """
                Is this file a "partial"-mode GIF where frames update a region of a different size to the entire image?
                If so, we need to construct the new frame by pasting it on top of the preceding frames.
                """
                if mode == "partial":
                    new_frame.paste(last_frame)

                new_frame.paste(im, (0, 0), im.convert("RGBA"))
                fh = NamedTemporaryFile(delete=False, suffix=".png")
                new_frame.save(fh.name, "PNG")
                fh.flush()

                ocr_io = NamedTemporaryFile("w+", delete=False)

                image_preview.add_image(
                    fh.name,
                    name=f"{request.file_name}_frame_{i}",
                    description="GIF frame",
                    ocr_heuristic_id=ocr_heuristic_id,
                    ocr_io=ocr_io,
                )
                # Tag any network IOCs found in OCR output
                self.tag_network_iocs(image_preview, ocr_io)

                _handle_ocr_output(ocr_io, fn_prefix=f"{request.file_name}_frame_{i}")

                i += 1
                last_frame = new_frame
                im.seek(im.tell() + 1)
        except EOFError:
            pass

    def execute(self, request: ServiceRequest):
        """Main Module. See README for details."""
        result = Result()
        displayable_image_path = request.file_path
        pillow_incompatible = False

        save_ocr_output = request.get_param("save_ocr_output")

        # Handle save_ocr_output parameter being a boolean or string
        if isinstance(save_ocr_output, bool):
            save_ocr_output = "as_extracted" if save_ocr_output else "no"
        else:
            save_ocr_output = save_ocr_output.lower()

        def _handle_ocr_output(ocr_io, fn_prefix):
            # Write OCR output as specified by submissions params
            if save_ocr_output == "no":
                return
            else:
                # Write content to disk to be uploaded
                if save_ocr_output == "as_extracted":
                    request.add_extracted(ocr_io.name, f"{fn_prefix}_ocr_output", description="OCR Output")
                elif save_ocr_output == "as_supplementary":
                    request.add_supplementary(ocr_io.name, f"{fn_prefix}_ocr_output", description="OCR Output")
                else:
                    self.log.warning(f"Unknown save method for OCR given: {save_ocr_output}")

        if request.file_type.split("/")[-1] in ["svg", "wmf", "emf"]:
            try:
                displayable_image_path = os.path.join(self.working_directory, f"{request.file_name}.png")
                if any([request.file_type.endswith(wmf_type) for wmf_type in ["wmf", "emf"]]):
                    # PIL is able to identify WMF but not able to render, therefore we need to convert
                    Image(filename=request.file_path).save(filename=displayable_image_path)
                elif request.file_type.endswith("svg"):
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
                ocr_io = NamedTemporaryFile("w+", delete=False)
                image_preview.add_image(
                    displayable_image_path,
                    name=request.file_name,
                    description="Input file",
                    ocr_heuristic_id=ocr_heuristic_id,
                    ocr_io=ocr_io,
                )
                # Tag any network IOCs found in OCR output
                self.tag_network_iocs(image_preview, ocr_io)

                _handle_ocr_output(ocr_io, fn_prefix=request.file_name)
            image_preview.promote_as_screenshot()
            result.add_section(image_preview)

            # Attempt QR code decoding
            qr_detected_section: Optional[ResultSection] = None
            qr_results = subprocess.run(["zbarimg", "-q", displayable_image_path], capture_output=True).stdout.decode()
            if not qr_results:
                # Try decoding with a color invert of the image
                with NamedTemporaryFile() as tmp_qr:
                    ImageOps.invert(PILImage.open(request.file_path).convert("RGB")).save(tmp_qr.name, format="JPEG")
                    qr_results = subprocess.run(["zbarimg", "-q", tmp_qr.name], capture_output=True).stdout.decode()

            if qr_results:
                for i, qr_result in enumerate(qr_results.split("\n")):
                    code_type, code_value = qr_result.split(":", 1)
                    if not qr_detected_section:
                        qr_heur = Heuristic(3)
                        qr_detected_section = ResultSection(qr_heur.name, heuristic=qr_heur, parent=result)
                    if re.match(FULL_URI, code_value):
                        qr_heur.add_signature_id("uri_decoded_from_qr_code")
                        # Tag URI
                        image_preview.add_tag("network.static.uri", code_value)
                        if request.get_param("extract_ocr_uri"):
                            request.add_extracted_uri("URI from QR code", code_value)
                    else:
                        qr_heur.add_signature_id("file_decoded_from_qr_code")
                        # Write data to file
                        fh = NamedTemporaryFile(delete=False, mode="w")
                        fh.write(code_value)
                        fh.close()

                        request.add_extracted(
                            fh.name, name=f"embedded_code_{i}", description=f"Decoded {code_type} content"
                        )
        except ValueError:
            pass
        except (PILImage.DecompressionBombError, OSError, UnidentifiedImageError):
            if displayable_image_path == request.file_path:
                pillow_incompatible = True

        steg_section = ResultMemoryDumpSection("Steganographical Analysis")
        # Attempt to extract files from the image
        extract_path = NamedTemporaryFile(delete=False)
        p = subprocess.run(
            ["stegseek", "-a", "-f", request.file_path, "/opt/al_service/rockyou.txt", extract_path.name],
            capture_output=True,
        ).stderr

        if b"Extracting to" in p:
            self.log.info("Embedded file extracted from image.")
            extracted_section = ResultKeyValueSection("Secret file was extracted from image", parent=steg_section)
            lines = [x for x in p.decode().splitlines() if "e: " in x]
            orig_name = "steg_extract.txt"
            passphrase = None
            for line in lines:
                if 'filename: "' in line:
                    orig_name = line.split('filename: "')[1][:-2]  # Original filename: "Hello.txt".
                if 'passphrase: "' in line:
                    passphrase = line.split('passphrase: "')[1].strip('"')  # Found passphrase: "pass"

            extracted_section.set_item("original_name", orig_name)
            if passphrase is not None:
                extracted_section.set_item("passphrase", passphrase)
            request.add_extracted(
                extract_path.name, orig_name, "File extracted from image", safelist_interface=self.api_interface
            )
            extracted_section.set_heuristic(2)

        if pillow_incompatible:
            # We can't proceed with further analysis because the original file is incompatible with Pillow
            request.result = result
            return

        secret_msg = None
        if "RGB" not in PILImage.open(request.file_path).mode:
            # Library expects an image containing RGB channels
            secret_msg = None
        elif not request.file_type.endswith("jpg") or request.deep_scan:
            try:
                secret_msg = lsb.reveal(request.file_path)
            except IndexError:
                # Unable to determine a secret message
                pass
        # Think it's unlikely to have both a hidden message and an embedded file
        if secret_msg:
            self.log.info("Secret message found.")
            steg_section.set_body(f"Secret message found:\n{secret_msg}")
            steg_section.set_heuristic(2)

        # Default to original behaviour
        else:
            # Find attached data
            additional_content = find_additional_content(request.file_contents)
            if additional_content:
                ares = ResultMemoryDumpSection("Possible Appended Content Found")
                ares.add_line("{} Bytes of content found at end of image file".format(len(additional_content)))
                ares.add_line("Text preview (up to 500 bytes):\n")
                ares.add_line("{}".format(safe_str(additional_content)[0:500]))
                ares.set_heuristic(2)
                result.add_section(ares)
                file_name = "{}_appended_img_content".format(hashlib.sha256(additional_content).hexdigest()[0:10])
                file_path = os.path.join(self.working_directory, file_name)
                with open(file_path, "wb") as unibu_file:
                    unibu_file.write(additional_content)
                request.add_extracted(
                    file_path, file_name, "Carved content found at end of image.", safelist_interface=self.api_interface
                )

        # Steganography modules
        try:
            img_info = ImageInfo(request.file_path, request, steg_section, self.working_directory, self.log)
            self.log.debug(f"Pixel Count: {img_info.pixel_count}")
            if (
                img_info.pixel_count > 100
                and img_info.pixel_count < self.config.get("max_pixel_count", 100000)
                or request.deep_scan
            ):
                img_info.decloak()

            if steg_section.body or steg_section.subsections:
                result.add_section(steg_section)
        except NotSupported:
            pass
        request.result = result
