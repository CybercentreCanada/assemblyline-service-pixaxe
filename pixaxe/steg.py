"""
Requires numpy, Pillow(PIL), python-matplotlib, scipy
"""
from assemblyline_v4_service.common.result import ResultSection, BODY_FORMAT

from PIL import Image
import json
import math
import numpy as np
from os import path
from scipy.stats import chisquare
import matplotlib.pyplot as plt


class NotSupported(Exception):
    pass


class ImageInfo(object):
    def __init__(self, i, request=None, result=None, working_directory=None):

        self.request = request
        self.result = result
        self.working_directory = working_directory

        if result:
            self.working_result = (ResultSection("Image Steganography Module Results:",
                                                 body_format=BODY_FORMAT.MEMORY_DUMP))
        else:
            self.result = result

        # Currently only supporting 8-bit pixel modes
        self.pixel_size = 8
        supported_modes = {
            'CMYK': 4,
            'P': 1,
            'RGB': 3,
            'RGBA': 4,
        }

        # Pillow seems to like non-corrupt images, so give its best shot and exit on error
        try:
            img = Image.open(i)
        except Exception:
            raise NotSupported()

        try:
            self.iformat = img.format
            self.imode = img.mode.upper()
            self.isize = img.size
        except Exception:
            raise NotSupported()

        if not self.iformat and not self.imode and not self.isize:
            # Something likely wrong
            raise NotSupported()

        if self.imode.upper() not in supported_modes:
            if not self.result:
                print("{} image mode not currently supported for steganlaysis modules".format(self.imode))
                exit()
            else:
                print("not a supported mode: {}".format(self.result))
                raise NotSupported()
        else:
            self.channels_to_process = supported_modes[self.imode]

        if result:
            pil_result = ResultSection("Pillow Image Data:", body_format=BODY_FORMAT.MEMORY_DUMP)
            if self.iformat:
                pil_result.add_line("Format:\t {}".format(self.iformat))
            if self.imode:
                pil_result.add_line("Mode:\t {}".format(self.imode))
                pil_result.add_tag('file.img.mode', self.imode)
            if self.isize:
                pil_result.add_line("Size:\t {}x{}".format(self.isize[0], self.isize[1]))
                pil_result.add_tag('file.img.size', "{}x{}".format(self.isize[0], self.isize[1]))
            self.result.add_section(pil_result)

        try:
            self.ipixels = iter(img.getdata())
        except Exception:
            raise NotSupported()

        try:
            img = Image.open(i)
            self.iobject = img.load()
        except Exception:
            raise NotSupported()

        self.binary_pixels = [self.convert_binary_string(self.imode, self.channels_to_process, self.ipixels)]
        self.pixel_count = (self.isize[0] * self.isize[1] * self.channels_to_process)

        # Chunk size equals (#bytes*8) bits/num byte-values per pixel. Therefore if 8 bits per pixel, and you want to
        # perform test on every 512 bytes of data, chunk size will be (512*8)/8 == every 512 pixels examined.
        # Optimize chunk size if this is being run through AL
        if request is not None:
            maximizer = self.pixel_count / 20000
            if maximizer == 0:
                maximizer = 1
            self.chunk = 128 * maximizer
        else:
            self.chunk = 256

        self.chunk = int(self.chunk)
        # total chunk bits/8
        self.chunk_bytes = (self.chunk * self.pixel_size * self.channels_to_process) / 8

    # --- Support Functions --------------------------------------------------------------------------------------------

    @staticmethod
    def convert_binary_string(mode, channels, p):

        if channels == 1:
            for pi in p:
                yield '{0:08b}'.format(pi)

        else:
            for pi in p:
                pset = ()
                for ip in pi[:channels]:
                    pset += ('{0:08b}'.format(ip),)
                if mode == 'RGBA':
                    pset += ('{0:08b}'.format(pi[-1]),)
                yield pset

    @staticmethod
    def extract_pixels(i):
        form = None
        mode = None
        size = None
        pixels = None
        # Pillow seems to like non-corrupt images, so give its best shot and exit on error
        try:
            img = Image.open(i)
            form = img.format
            mode = img.mode.upper()
            size = img.size
        except Exception:
            raise NotSupported()
        try:
            pixels = list(img.getdata())
        except Exception:
            raise NotSupported()
        return form, mode, size, pixels

    def get_colours(self, pixels, raw=False):
        if raw:
            colours = {self.imode[x]: pixels[x] for x in range(0, self.channels_to_process)}
            return colours

        colour_format = {self.imode[x]: x for x in range(0, self.channels_to_process)}
        colours = {self.imode[x]: [] for x in range(0, self.channels_to_process)}

        for p in pixels:
            for c, pos in iter(colour_format.items()):
                colours[c].append(p[pos])

        return colours

    def detect_sig_changes(self, data, thr_counter=0.5):
        sig_val = []
        # Iterate through data to find if there is a significant change in values, if there is, record position
        for i, (x, y) in enumerate(zip(data, data[1:])):
            if x + y == 0:
                continue
            thr = float(thr_counter * y)
            if x >= float(y) + thr or x <= float(y) - thr:
                sig_val.append(i + 1)

        if len(sig_val) > 0:
            sig_res = ResultSection('Found significant change in randomness')
            # Only account for LSB, therefore 1 bit per pixel, not 8
            bits_per_group = self.chunk * self.channels_to_process
            if len(sig_val) == 1:
                for start in sig_val:
                    total_plot_span = (len(data) - start) + 1
                    bytes_of_embed = int(round(float((total_plot_span * bits_per_group) / 8), 0))
                    total_bytes = int(round(float((start * bits_per_group) / 8), 0))
                    sig_res.add_line("{} bytes of possible random embedded data starting around byte {} of image."
                                     .format(bytes_of_embed, total_bytes))
            else:
                for i, (start, end) in enumerate(zip(sig_val, sig_val[1:])):
                    total_plot_span = (end - start) + 1
                    bytes_of_embed = int(round(float((total_plot_span * bits_per_group) / 8), 0))
                    total_bytes = int(round(float((start * bits_per_group) / 8), 0))
                    sig_res.add_line("{} bytes of possible random embedded data starting around byte {} of image."
                                     .format(bytes_of_embed, total_bytes))

            return sig_res

        return

    def iter_grayscale_pixels(self):
        for pi in self.binary_pixels:
            if int(pi[-1]) == 0:
                yield 0
            else:
                yield 255

    def iter_rgba_pixels(self):
        for pi in self.binary_pixels:
            pset = ()
            for ip in pi[:self.channels_to_process]:
                if int(ip[-1]) == 0:
                    pset += (0,)
                else:
                    pset += (255,)

            if self.imode == 'RGBA':
                pset += (int(pi[-1], 2),)
            yield pset

    # --- LSB Functions ------------------------------------------------------------------------------------------------
    # 1
    def LSB_visual(self):
        """Convert pixel data so that each value in a pixel is either 0 (if LSB == 0) or 255 (if LSB == 1)"""
        img = Image.new(self.imode, self.isize)
        if self.working_directory is None:
            self.working_directory = path.dirname(__file__)
        try:
            if self.channels_to_process == 1:
                img.putdata(self.iter_grayscale_pixels())
                success = True
            else:
                img.putdata(self.iter_rgba_pixels())
                success = True
        except:
            success = False

        if success:
            lsb_visual_path = path.join(self.working_directory, "LSB_visual_attack.{}".format(self.iformat.lower()))
            img.save(lsb_visual_path)
            # Save to AL supplementary file. Request should therefore be set and working_directory given.
            if self.request is not None:
                self.request.add_supplementary(lsb_visual_path, "LSB_visual_attack", "Pixaxe LSB visual attack image")
                if self.result is not None:
                    visres = ResultSection('Visual LSB Analysis.\t')
                    visres.add_line('Visual LSB analysis successful, see extracted files.')
                    self.working_result.add_subsection(visres)
            else:
                img.show()
        return

    # 2
    def LSB_chisquare(self):
        pixels = self.binary_pixels

        x_points = []
        y_points = []

        # Use image if not in AL
        if self.request is None:
            plt.switch_backend('agg')
            plt.axis([0, self.pixel_count / 8, -0.1, 1.1])
            plt.title('Chi Square Test')
            plt.grid(True)

        index = 0
        success = False

        try:
            # If greyscale, only one set of pixels to process
            if self.channels_to_process == 1:
                while len(pixels) != 0:
                    print(len(pixels))
                    # In bytes
                    x_location = (self.chunk * self.channels_to_process) * index / 8
                    x_points.append(x_location)

                    obs_pixel_set = []
                    exp_pixel_set = []
                    # Let's grab some PoVs!!! Yay!!!
                    for i in range(0, 255, 2):
                        # Get counts
                        v1 = pixels[:self.chunk].count(str('{0:08b}').format(i))
                        v2 = pixels[:self.chunk].count(str('{0:08b}').format(i + 1))
                        # Add observed values
                        if v1 == 0 and v2 == 0:
                            continue
                        obs_pixel_set.append(v1)
                        obs_pixel_set.append(v2)
                        # Calculate expected values of pairs
                        expected = float((v1 + v2) * 0.5)
                        exp_pixel_set.extend([expected] * 2)

                    if len(obs_pixel_set) == 0:
                        y_points.append(0)
                    else:
                        y_points.append(round(chisquare(np.array(obs_pixel_set), f_exp=np.array(exp_pixel_set))[1], 4))

            else:
                # If not greyscale, test each colour channel separately per chunk and then average
                while len(pixels) != 0:
                    x_location = (self.chunk * self.channels_to_process) * index / 8
                    x_points.append(x_location)

                    # Grab channel (i.e. R,G,B) pixels
                    colours = self.get_colours(pixels[:self.chunk])
                    counts = []
                    lsb_counts = []

                    for c, pixels_flat in iter(colours.items()):
                        obs_pixel_set = []
                        exp_pixel_set = []
                        # Let's grab some PoVs!!! Yay!!!
                        for i in range(0, 255, 2):
                            # Get counts
                            v1 = pixels_flat[:self.chunk].count(str('{0:08b}').format(i))
                            v2 = pixels_flat[:self.chunk].count(str('{0:08b}').format(i + 1))
                            # Add observed values
                            if v1 == 0 and v2 == 0:
                                continue
                            obs_pixel_set.append(v1)
                            obs_pixel_set.append(v2)
                            # Calculate expected values of pairs
                            expected = float((v1 + v2) * 0.5)
                            exp_pixel_set.extend([expected] * 2)

                        if len(obs_pixel_set) == 0:
                            counts.append(0)
                            if self.request is None:
                                plt.scatter(x_location, 0, color=c, marker='^', s=50)

                        else:
                            chi = round(chisquare(np.array(obs_pixel_set), f_exp=np.array(exp_pixel_set))[1], 6)
                            counts.append(chi)
                            if self.request is None:
                                plt.scatter(x_location, chi, color=c, marker='^', s=50)
                        # Additionally, collect the LSBs for additional randomness testing.
                        # Idea from http://guillermito2.net/stegano/tools/
                        lsb = []
                        for pbyte in pixels_flat:
                            lsb.append(float(pbyte[-1]))
                        lsb_avg_value = float(round(sum(lsb) / len(lsb), 1))
                        if self.request is None:
                            plt.scatter(x_location, lsb_avg_value, color='k', marker='.', s=10)
                        lsb_counts.append(lsb_avg_value)

                    # Average significance counts for the colours and round two 2 decimals
                    y_points.append(round(sum(counts) / self.channels_to_process, 2))

                    index += 1
                    pixels = pixels[self.chunk:]
                    success = True
        except:
            success = False

        if success:
            if self.request is None:
                plt.plot(x_points, y_points, 'm--', linewidth=1.0)
                lsb_chi_path = path.join(self.working_directory, "LSB_chiqquare_attack.png")
                plt.savefig(lsb_chi_path, bbox_inches='tight')
                plt.show()
            else:
                chi_graph_data = {
                    'type': 'colormap',
                    'data': {
                        'domain': [0, 100],
                        'values': [y * 100 for y in y_points]
                    }
                }

                chires = ResultSection('LSB Chi Square Analysis.\t')

                chires.add_subsection(ResultSection('Colour Map.'
                                                    '0==Not random, '
                                                    '100==Random'.format(self.chunk_bytes),
                                                    body_format=BODY_FORMAT.GRAPH_DATA,
                                                    body=json.dumps(chi_graph_data)))

                pval_res = self.detect_sig_changes(y_points)
                if pval_res:
                    chires.add_subsection(pval_res)
                self.working_result.add_subsection(chires)

        return

    # 3
    def LSB_averages(self):
        # Additionally, collect the LSBs for additional randomness testing.
        # Idea from http://guillermito2.net/stegano/tools/
        # Right now only supports AL
        if not self.request:
            return

        pixels = self.binary_pixels
        lsb_points = []
        success = False

        try:
            # If greyscale, only one set of pixels to process
            if self.channels_to_process == 1:
                while len(pixels) != 0:
                    lsb = []
                    for pbyte in pixels:
                        lsb.append(float(pbyte[-1]))
                    lsb_avg_value = round(sum(lsb) / len(lsb), 1)
                    lsb_points.append(lsb_avg_value)
                    pixels = pixels[self.chunk:]
                    success = True

            else:
                lsb_points_channels = {}
                # If not greyscale, test each colour channel separately per chunk and then average
                while len(pixels) != 0:
                    # Grab channel (i.e. R,G,B) pixels
                    colours = self.get_colours(pixels[:self.chunk])
                    lsb_counts = []

                    for c, pixels_flat in iter(colours.items()):
                        lsb = []
                        for pbyte in pixels_flat:
                            lsb.append(float(pbyte[-1]))
                        lsb_avg_value = float(round(sum(lsb) / len(lsb), 1))
                        lsb_counts.append(lsb_avg_value)
                        if lsb_points_channels.get(c, None):
                            lsb_points_channels[c].append(lsb_avg_value)
                        else:
                            lsb_points_channels[c] = []
                            lsb_points_channels[c].append(lsb_avg_value)

                    # Average lsb counts for the colours and round two 2 decimals
                    lsb_points.append(round(sum(lsb_counts) / self.channels_to_process, 2))

                    pixels = pixels[self.chunk:]
                    success = True
        except:
            success = False

        if success:
            lsb_graph_data = {
                'type': 'colormap',
                'data': {
                    'domain': [0, 100],
                    'values': [y * 100 for y in lsb_points]
                }
            }

            lsbres = ResultSection('LSB Average Value Analysis.\t')

            lsbres.add_subsection(ResultSection('Overall'
                                                'Closer to 0.5==Random, '
                                                'Closer to 0/100==Not Random.'.format(self.chunk_bytes),
                                                body_format=BODY_FORMAT.GRAPH_DATA,
                                                body=json.dumps(lsb_graph_data)))

            pval_res = self.detect_sig_changes(lsb_points, thr_counter=0.80)
            if pval_res:
                lsbres.add_subsection(pval_res)

            self.working_result.add_subsection(lsbres)

        return

    # 4
    def LSB_couples(self):
        """
        Was able to convert math theory to Python code from Java code found here:
        https://github.com/b3dk7/StegExpose/blob/master/SamplePairs.java
        """
        success = False
        width = self.isize[0]
        height = self.isize[1]
        # P =   num of pairs
        # W =   num of pairs where 7 msb are the same, but the lsb are different
        # X =   num of pairs where :
        #       p2 lsb is even (lsb=0) and p2 > p1
        #       OR
        #       p2 lsb is odd (lsb=1) and p2 < p1
        # Y =   num pairs where :
        #       p2 lsb is even (lsb=0) and  p2 < p1
        #       OR
        #       p2 lsb is odd (lsb=1) and p2 > p1
        # Z =   num of pairs that are the same

        results = {
            'P': 0,
            'W': 0,
            'X': 0,
            'Y': 0,
            'Z': 0,
            'a': 0,
            'b': 0,
            'c': 0,
            'final': float(0),
            'rd': 0,
        }

        # Greyscale images
        try:
            if self.channels_to_process == 1:

                # Pairs across image
                for he in range(height):
                    for wi in range(0, width - 1, 2):
                        if wi + 1 > width:
                            break
                        # Get sample pairs
                        s1 = self.iobject[wi, he]
                        s2 = self.iobject[wi + 1, he]

                        results['P'] += 1
                        # Is Z?
                        if s1 == s2:
                            results['Z'] += 1
                            continue
                        s1b = '{0:08b}'.format(s1)
                        s2b = '{0:08b}'.format(s2)
                        # Is W?
                        if s1b[:6] == s2b[:6] and s1b[7] != s2b[7]:
                            results['W'] += 1
                        # Is X? -- Lower value is odd
                        if (s2b[7] == '0' and int(s2b) > int(s1b)) or (s2b[7] == '1' and int(s2b) < int(s1b)):
                            results['X'] += 1
                        # Is Y? -- Lower value is even
                        if (s2b[7] == '0' and int(s2b) < int(s1b)) or (s2b[7] == '1' and int(s2b) > int(s1b)):
                            results['Y'] += 1

                # Pairs down image
                for wi in range(width):
                    for he in range(0, height - 1, 2):
                        if he + 1 > height:
                            break
                        # Get sample pairs
                        s1 = self.iobject[wi, he]
                        s2 = self.iobject[wi, he + 1]

                        results['P'] += 1
                        # Is Z?
                        if s1 == s2:
                            results['Z'] += 1
                            continue
                        s1b = '{0:08b}'.format(s1)
                        s2b = '{0:08b}'.format(s2)
                        # Is W?
                        if s1b[:6] == s2b[:6] and s1b[7] != s2b[7]:
                            results['W'] += 1
                        # Is X?
                        if (s2b[7] == '0' and int(s2b) > int(s1b)) or (s2b[7] == '1' and int(s2b) < int(s1b)):
                            results['X'] += 1
                        # Is Y?
                        if (s2b[7] == '0' and int(s2b) < int(s1b)) or (s2b[7] == '1' and int(s2b) > int(s1b)):
                            results['Y'] += 1

                # quadratic equation is: ax ^ 2 + bx + c = 0
                a = float(0.5 * (results['W'] + results['Z']))
                results['a'] = a
                b = float(2 * results['X'] - results['P'])
                results['b'] = b
                c = float(results['Y'] - results['X'])
                results['c'] = c

                # If a == 0, assume straight line
                if a == 0:
                    results['final'] = abs(float(c / b))
                else:
                    # Else take result as a curve
                    discriminant = float(b ** 2) - (4 * a * c)
                    if discriminant >= 0:
                        rootpos = abs(float(((-1 * b) + math.sqrt(discriminant)) / (2 * a)))
                        rootneg = abs(float(((-1 * b) - math.sqrt(discriminant)) / (2 * a)))

                        # return root with the smallest absolute value (as per paper)
                        if rootpos <= rootneg:
                            results['final'] = rootpos
                        else:
                            results['final'] = rootneg
                    else:
                        results['final'] = "Something likely wrong"

                # In Andrew Ker's paper, "Improved Detection of LSB Steganography in Grayscale Images" he suggests
                # dropping the message length (quadraic formula) and using relative difference instead ((Q-Q')/(Q+Q')).
                # Will be a Pvalue 0f 0.0 to 1.0

                e = float(results['Y'])
                o = float(results['X'])
                rd = abs((e - o) / (e + o))

                results['rd'] = rd

            # Other images
            else:
                colour_results = {self.imode[x]: dict(results) for x in range(0, self.channels_to_process)}

                # Pairs across image
                for he in range(height):
                    for wi in range(0, width - 1, 2):
                        # Get sample pairs
                        s1 = self.get_colours(list(self.iobject[wi, he]), raw=True)
                        s2 = self.get_colours(list(self.iobject[wi + 1, he]), raw=True)

                        for k, i in iter(s1.items()):
                            colour_results[k]['P'] += 1
                            # Is Z?
                            if i == s2[k]:
                                colour_results[k]['Z'] += 1
                                continue
                            s1b = '{0:08b}'.format(i)
                            s2b = '{0:08b}'.format(s2[k])
                            # Is W?
                            if s1b[:6] == s2b[:6] and s1b[7] != s2b[7]:
                                colour_results[k]['W'] += 1
                            # Is X? -- Lower value is odd
                            if (s2b[7] == '0' and int(s2b) > int(s1b)) or (s2b[7] == '1' and int(s2b) < int(s1b)):
                                colour_results[k]['X'] += 1
                            # Is Y? -- Lower value is even
                            if (s2b[7] == '0' and int(s2b) < int(s1b)) or (s2b[7] == '1' and int(s2b) > int(s1b)):
                                colour_results[k]['Y'] += 1

                # Pairs down image
                for wi in range(width):
                    for he in range(0, height - 1, 2):
                        # Get sample pairs
                        s1 = self.get_colours(list(self.iobject[wi, he]), raw=True)
                        s2 = self.get_colours(list(self.iobject[wi, he + 1]), raw=True)

                        for k, i in iter(s1.items()):
                            colour_results[k]['P'] += 1
                            # Is Z?
                            if i == s2[k]:
                                colour_results[k]['Z'] += 1
                                continue
                            s1b = '{0:08b}'.format(i)
                            s2b = '{0:08b}'.format(s2[k])
                            # Is W?
                            if s1b[:6] == s2b[:6] and s1b[7] != s2b[7]:
                                colour_results[k]['W'] += 1
                            # Is X?
                            if (s2b[7] == '0' and int(s2b) > int(s1b)) or (s2b[7] == '1' and int(s2b) < int(s1b)):
                                colour_results[k]['X'] += 1
                            # Is Y?
                            if (s2b[7] == '0' and int(s2b) < int(s1b)) or (s2b[7] == '1' and int(s2b) > int(s1b)):
                                colour_results[k]['Y'] += 1

                for k, i in iter(colour_results.items()):
                    a = float(0.5 * (colour_results[k]['W'] + colour_results[k]['Z']))
                    colour_results[k]['a'] = a
                    b = float(2 * colour_results[k]['X'] - colour_results[k]['P'])
                    colour_results[k]['b'] = b
                    c = float(colour_results[k]['Y'] - colour_results[k]['X'])
                    colour_results[k]['c'] = c

                    # If a == 0, assume straight line
                    if a == 0:
                        colour_results[k]['final'] = abs((float(c / b)))
                    else:
                        # Else take result as a curve
                        discriminant = float(b ** 2) - (4 * a * c)
                        if discriminant >= 0:
                            rootpos = abs(float(((-1 * b) + math.sqrt(discriminant)) / (2 * a)))
                            rootneg = abs(float(((-1 * b) - math.sqrt(discriminant)) / (2 * a)))

                            # return root with the smallest absolute value (as per paper)
                            if rootpos <= rootneg:
                                colour_results[k]['final'] = rootpos
                            else:
                                colour_results[k]['final'] = rootneg
                        else:
                            colour_results[k]['final'] = "Something likely wrong"

                    # In Andrew Ker's paper, he suggests dropping the message length (quadraic formula) and using
                    # relative difference instead ((Q-Q')/(Q+Q')). Will be a value 0f 0.0 to 1.0
                    e = float(colour_results[k]['Y'])
                    o = float(colour_results[k]['X'])
                    rd = abs((e - o) / (e + o))

                    colour_results[k]['rd'] = rd

                results = colour_results

            success = True
        except:
            success = False

        if success:
            final_body = ""
            lenfinal = 0
            rdfinal = 0
            divd = self.channels_to_process
            for k, i in iter(results.items()):
                if i['final'] == "Something likely wrong":
                    final_body += "{0} Pixel Results: {1}\n".format(k, i['final'])
                    divd -= 1
                else:
                    final_body += "{0} Pixel Results: {1}%\n".format(k, i['final'] * 100)
                    lenfinal += i['final']
                rdfinal += i['rd']
            if divd == 0:
                avg_lenfinal = 0
            else:
                avg_lenfinal = float(lenfinal / divd) * 100
            avg_rdfinal = float(rdfinal / self.channels_to_process)
            final_body += "Likelyhood of hidden message: {} (P value)." \
                          "\nCombined length results: {}% of image possibly embedded with a hidden message." \
                .format(avg_rdfinal, avg_lenfinal)
            if self.result is not None:
                score = int(round(avg_lenfinal + (avg_rdfinal * 10), 0))
                self.working_result.add_subsection(ResultSection(title_text='LSB Couples Analysis',
                                                                 body_format=BODY_FORMAT.MEMORY_DUMP,
                                                                 body=final_body))
            else:
                print("\t {}".format(final_body))

        return

    def decloak(self):
        supported = {
            1: {self.LSB_visual: ['CMYK', 'P', 'RGB', 'RGBA', ]},
            2: {self.LSB_chisquare: ['CMYK', 'P', 'RGB', 'RGBA', ]},
            3: {self.LSB_averages: ['CMYK', 'P', 'RGB', 'RGBA', ]},
            4: {self.LSB_couples: ['CMYK', 'P', 'RGB', 'RGBA', ]},
        }
        for k, d in sorted(iter(supported.items())):
            for mod, l in iter(d.items()):
                if self.imode in l:
                    mod()
        if len(self.working_result.subsections) > 0:
            self.result.add_section(self.working_result)

        return
