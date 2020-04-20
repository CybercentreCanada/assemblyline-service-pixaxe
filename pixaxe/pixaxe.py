from assemblyline_v4_service.common.base import ServiceBase
from assemblyline_v4_service.common.result import Heuristic, Result, ResultSection, BODY_FORMAT
from assemblyline.common.str_utils import safe_str
from assemblyline_v4_service.common.utils import TimeoutException, set_death_signal
from functools import reduce

# from assemblyline.al.service.base import ServiceBase
# from assemblyline.al.common.heuristics import Heuristic
# from assemblyline.al.common.result import Result, ResultSection, SCORE, TAG_TYPE, TAG_WEIGHT, BODY_FORMAT
# from assemblyline.common.charset import safe_str
# from assemblyline.common.reaper import set_death_signal
# from assemblyline.common.timeout import SubprocessTimer, TimeoutException

from textwrap import dedent


class Pixaxe(ServiceBase):
    PAT_FILEMARKERS = {
        # Header, Trailer, additional methods
        'bmp': ['\x42\x4D', None, 'bmp_dump'],
        'gif': ['\x47\x49\x46\x38.\x61.{19,}\x2C.{9,}', '\x00\x3B', None],
        'jpeg': ['\xFF\xD8.{18}\xFF\xDB.{3,}\xFF\xDA.{13,}', '\xFF\xD9', None],
        'jpeg2000': ['\x00\x00\x00\x0C\x6A\x50\x20\x20\x0D\x0A', None, 'jp2_dump'],
        'png': ['\x89\x50\x4E\x47', '\x49\x45\x4E\x44.{4}', None],
    }
    XMP_TAGGED_VALUES = {
        'DOCUMENT ID': 'XMP_DOCUMENT_ID',
        'DERIVED FROM DOCUMENT ID': 'XMP_DERIVED_DOCUMENT_ID',
        'INSTANCE ID': 'XMP_INSTANCE_ID',
        'XMP TOOLKIT': 'XMP_TOOLKIT',
        'CREATOR TOOL': 'XMP_CREATOR_TOOL'
    }

    def __init__(self, config=None):
        super(Pixaxe, self).__init__(config)
        self.sha = None

    def start(self):
        self.log.debug("Pixaxe service started")

    def import_service_deps(self):
        global deepcopy, hashlib, magic, os, re, struct, subprocess
        global ImageInfo, NotSupported
        from pixaxe.steg import ImageInfo, NotSupported
        from copy import deepcopy
        import hashlib
        import magic
        import os
        import re
        import struct
        import subprocess
        return

    @staticmethod
    def getfromdict(data, mapList):
        try:
            match = reduce(lambda d, k: d[k], mapList, data)
        except KeyError:
            match = None
        return match

    def setindict(self, data, mapList, value):
        """Sets value in a nested dictionary using getfromdict method.

        Args:
            data: Dictionary to input data.
            mapList: List of dictionary keys to iterate through.
            value: Value of final key to place in dictionary.

        Returns:
            Dictionary with new value, or None if KeyError.
        """
        self.getfromdict(data, mapList[:-1])[mapList[-1]] = value

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
        try:
            # Byte offset to start of image
            soi = struct.unpack('<I', data[10:14])[0]
            # Size of image data, including padding -- potentially unrealiable
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
        except:
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
                print(file_type)
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
        except:
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
        for ftype, tinfo in self.PAT_FILEMARKERS.iteritems():

            # Build up the regex
            if tinfo[1] is not None:
                embed_regex = re.compile(tinfo[0] + '.+' + tinfo[1], re.DOTALL)
            else:
                embed_regex = re.compile(tinfo[0] + '.+', re.DOTALL)

            # Find the pattern that should match the image.
            img_match = re.match(embed_regex, data)
            if img_match:
                img_data = img_match.group()
                # Go to extraction module if there is one
                if tinfo[2] is not None:
                    img_data = getattr(self, tinfo[2])(img_data)

                # Otherwise extract data as-is (regex is considered good enough)
                leftovers = data.replace(img_data, "")

                # Remove trailing NULL bytes
                leftovers = re.sub('[\x00]*$', '', leftovers)

                if len(leftovers) > 15:
                    return leftovers
        return

    def call_exiftools(self, infile):
        """Runs command-line tool Exiftools. Arguments:
         -ee Extract information from embedded files
         -G Print group name for each tag
         -m Ignore minor errors and warnings
         -q Quiet processing
         -t Tab separated
         -x TAG Exclude specified file TAGs
         --PDF:* Exlude PDF parser (timeouts)

        Args:
            infile: File path.

        Returns:
            Standard output and error output of command.
        """
        cmd = ["exiftool", "-a", "-ee", "-G", "-m", "-t", "-x", "Directory", "-x", "File*", "-x", "MIMEType", '--PDF:*',
               infile]
        return self.process(command=cmd, name="exiftool")

    def call_exiftools_extract(self, infile, k):
        """Runs command-line tool Exiftools to extract binary metadata. Arguments:
         -b Binary output
         -{} item to extract
        Args:
            infile: File path.
            k: String of metadata item to extract.

        Returns:
            Standard output and error output of command.
        """
        cmd = ["exiftool", "-b", "-{}".format(k.replace(' ', "")), infile]
        return self.process(command=cmd, name="exiftool extract")

    def tesseract_call(self, file_path, outfile):
        """Runs command-line tool Tesseract. Arguments:

        Args:
            infile: File path.
            outfile: File path of output data.

        Returns:
            Standard output and error output of command.
        """
        cmd = ['tesseract', file_path, outfile]
        # Process the command and save the csv result in the result object
        return self.process(command=cmd, name="tesseract")

    def convert_img(self, infile, outfile):
        """Runs command-line tool convert. Arguments:
        # -resize 200% Enlarge image by 200%

        Args:
            infile: File path.
            outfile: File path of output data.

        Returns:
            Standard output and error output of command.
        """
        cmd = ['convert', '-resize', '200%', infile, outfile]
        return self.process(command=cmd, name="convert")

    def process(self, command, name):
        """Runs command-line tool argument using the subprocess module.

        Args:
            command: List of command-line arguments.
            name: Name of application being run (for logger output).

        Returns:
            Standard output and error output of command.
        """
        try:
            # with SubprocessTimer(self.config['COMMAND_TIMEOUT']) as timer:
            process = subprocess.run(command,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     preexec_fn=set_death_signal(),
                                     timeout=self.config['COMMAND_TIMEOUT'])
            process.wait()
            stdout, stderr = process.communicate()
            if stderr:
                if len(stderr) == 0:
                    stderr = None
        except TimeoutException as e:
            self.log.debug("Timeout exception for file {}, with process {}:".format(self.sha, name) + e.message)
            stdout = None
            stderr = None
        except Exception as e:
            self.log.warning("{} failed to run on sample {}. Reason: ".format(name, self.sha) + e.message)
            stdout = None
            stderr = None
        return stdout, stderr

    def assess_output(self, output, req):
        """Filters and writes output produced by OCR engine Tesseract.

        Args:
            output: Path to CSV file containing Tesseract output.
            req: AL request object (to submit extracted file).

        Returns:
            Filtered output string, or NULL string if no usable output found.
        """
        ocr_strings = ""
        output = "{}.txt".format(output)
        if os.path.getsize(output) == 0:
            return False
        filtered_lines = set()
        filtered_output = os.path.join(self.working_directory, "filtered_output.txt")
        with open(output, 'rb') as f:
            lines = f.readlines()

        for l in lines:
            safe_l = safe_str(l)
            # Test number of unique characters
            uniq_char = ''.join(set(safe_l))
            if len(uniq_char) > 5:
                filtered_lines.add(safe_l + "\n")

        if len(filtered_lines) == 0:
            return None

        with open(filtered_output, 'wb') as f:
            f.writelines(filtered_lines)

        for fl in filtered_lines:
            ocr_strings += fl

        req.add_extracted(filtered_output, "Filtered strings extracted via OCR", "output.txt")
        return ocr_strings

    def execute(self, request):
        """Main Module. See README for details."""
        result = Result()
        request.result = result
        self.sha = request.sha256
        infile = request.download()
        run_steg = request.get_param('run_steg')

        bin_extracted = set()

        # Attempt to scan file with exiftool and extract any binary data in meta that is over 50 bytes.
        stdout, stderr = self.call_exiftools(infile)
        file_info = {}

        if stdout:
            for li in stdout.split("\n"):
                if "\t" in li:
                    if li.split("\t")[2]:
                        if self.getfromdict(file_info, [li.split("\t")[0]]):
                            self.setindict(file_info, [li.split("\t")[0], li.split("\t")[1]], li.split("\t")[2])
                        else:
                            self.setindict(file_info, [li.split("\t")[0]], {li.split("\t")[1]: li.split("\t")[2]})

            # Extract any binary information over 50 bytes
            for k, i in file_info.iteritems():
                for sk, si in i.iteritems():
                    if si.startswith("(Binary data"):
                        bresult, stderr = self.call_exiftools_extract(infile, sk)
                        if bresult:
                            binhash = hashlib.sha256(bresult).hexdigest()
                            if binhash in bin_extracted:
                                continue
                            bin_extracted.add(binhash)
                            # space\carraige return\new line\null\0
                            if len(bresult.rstrip('0 \t\r\n\0')) < 50:
                                continue
                            result.report_heuristic(self.AL_PIXAXE_002)
                            file_path = os.path.join(self.working_directory, "{}_binary_meta"
                                                     .format(binhash[0:10]))
                            request.add_extracted(file_path, "Extracted binary data from ExifTools output.")
                            with open(file_path, 'wb') as unibu_file:
                                unibu_file.write(bresult)

            if not stderr:
                trv_dic = True
                if len(file_info.keys()) == 1:
                    if file_info.keys()[0].upper() == 'EXIFTOOL':
                        trv_dic = False
                if trv_dic:
                    eres = (ResultSection("ExifTools Results", body_format=BODY_FORMAT.MEMORY_DUMP))
                    exif_res = (ResultSection("File Info:", body_format=BODY_FORMAT.MEMORY_DUMP,
                                              parent=eres))
                    recognized_ftype = True
                    for k, i in file_info.iteritems():
                        ku = k.upper()
                        subexi_res = (ResultSection("::{} DATA::".format(ku),
                                                    body_format=BODY_FORMAT.MEMORY_DUMP, parent=exif_res))
                        meta_list = []
                        for lk, li in i.iteritems():
                            # Output for unknown file type will not go to stderr
                            if ku == 'EXIFTOOL' and li == 'Unknown file type':
                                recognized_ftype = False
                                self.log.debug('File type for sample {} not supported by EXIFTOOLS'.format(self.sha))
                                continue
                            lku = lk.upper()
                            mvalue = '{0}: {1}'.format(lk, li)
                            subexi_res.add_line(mvalue)
                            # Take out dates from meta hash (calculated below)
                            if 'date' not in mvalue.lower():
                                meta_list.append(mvalue)
                            # Look for specific metadata to tag
                            if ku == 'COMPOSITE':
                                if lku == 'MEGAPIXELS':
                                    exif_res.add_tag('IMAGE_MEGAPIXELS',
                                                     str(li))
                            if ku == 'XMP':
                                if lku in self.XMP_TAGGED_VALUES:
                                    exif_res.add_tag('EXIFTOOL_{}'.format(self.XMP_TAGGED_VALUES[lku]),
                                                     str(li))
                        # Create a hash of each metadata section
                        if ku not in ['COMPOSITE', 'EXIFTOOL']:
                            meta_hash = hashlib.sha1(" ".join(sorted(meta_list))).hexdigest()
                            exif_res.add_tag('SORTED_METADATA_HASH',
                                             "{}:{}".format(ku, meta_hash))

                    if recognized_ftype:
                        result.report_heuristic(self.AL_PIXAXE_001)
                        result.add_section(eres)

        # Run image-specific modules
        supported_images = re.compile('image/(bmp|gif|jpeg|jpg|png)')
        if re.match(supported_images, request.tag):
            # Extract img info using Pillow (already available in steg.py) and determine if steg modules should be run
            if self.config['RUN_STEG_AUTO'] or run_steg:
                decloak = True
            else:
                decloak = False
            try:
                imginfo = ImageInfo(infile, request, result, self.working_directory)
            except NotSupported:
                decloak = False

            # Run Tesseract on sample
            # Process the command and save the csv result in the result object
            usable_out = None
            orig_outfile = os.path.join(self.working_directory, 'outfile')
            stdout, stderr = self.tesseract_call(infile, orig_outfile)

            if stdout or stderr:
                # Assess Tesseract warnings
                if "pix too small" in stderr:
                    # Make the image larger with convert command
                    c_outfile = os.path.join(self.working_directory, 'enlrg_img')
                    c_stdout, c_stderr = self.convert_img(infile, c_outfile)
                    if c_stdout:
                        c_outfile = os.path.join(self.working_directory, 'c_outfile')
                        enlrg_infile = os.path.join(self.working_directory, 'enlrg')
                        if not c_stderr:
                            stdout, stderr = self.tesseract_call(enlrg_infile, c_outfile)
                            if stdout:
                                if not stderr:
                                    outfile = c_outfile
                                else:
                                    outfile = orig_outfile
                            else:
                                outfile = orig_outfile
                        else:
                            outfile = orig_outfile
                    else:
                        outfile = orig_outfile
                else:
                    outfile = orig_outfile
                    self.log.debug("Tesseract errored/warned on sample {}. Error:{}".format(self.sha, stderr))

                usable_out = self.assess_output(outfile, request)

            if usable_out:
                result.report_heuristic(self.AL_PIXAXE_003)
                ores = ResultSection("OCR Engine detected strings in image",
                                     body_format=BODY_FORMAT.MEMORY_DUMP)
                ores.add_line("Text preview (up to 500 bytes):\n")
                ores.add_line("{}".format(usable_out[0:500]))
                result.add_section(ores)

            # Find attached data
            additional_content = self.find_additional_content(infile)
            if additional_content:
                result.report_heuristic(self.AL_PIXAXE_004)
                ares = (ResultSection("Possible Appended Content Found",
                                      body_format=BODY_FORMAT.MEMORY_DUMP))
                ares.add_line("{} Bytes of content found at end of image file".format(len(additional_content)))
                ares.add_line("Text preview (up to 500 bytes):\n")
                ares.add_line("{}".format(safe_str(additional_content)[0:500]))
                result.add_section(ares)
                file_path = os.path.join(self.working_directory, "{}_appended_img_content"
                                         .format(hashlib.sha256(additional_content).hexdigest()[0:10]))
                request.add_extracted(file_path, "Carved content found at end of image.")
                with open(file_path, 'wb') as unibu_file:
                    unibu_file.write(additional_content)

            # Steganography modules
            if decloak:
                imginfo.decloak()
