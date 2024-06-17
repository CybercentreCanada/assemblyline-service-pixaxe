import magic
import re
import struct


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


def bmp_dump(data):
    """BMP embedded file extraction. Looks for traits of known BMP file structure to find embedded BMP data.

    Args:
        data: Raw data to search.

    Returns:
        BMP data if discovered, or original data.
    """
    # noinspection PyBroadException
    try:
        # Byte offset to start of image
        soi = struct.unpack("<I", data[10:14])[0]
        # Size of image data, including padding -- potentially unreliable
        sizei = struct.unpack("<I", data[34:38])[0]
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
        bmp_data = data[0 : (soi + sizei)]
        verify_bmp = mimetype(bmp_data, "image")
        if not verify_bmp:
            return data
        return bmp_data
    except Exception:
        return data


def jpg2_dump(data):
    """Looks for traits of known JPEG 2000 file structure to confirm that data is likely JPEG 2000 data.

    Args:
        data: Raw data to search.

    Returns:
        JPEG 2000 data if discovered, or original data.
    """
    ftyps = {
        "\x6a\x70\x32\x20": "jp2",
        "\x6a\x70\x78\x20": "jpf",
        "\x6a\x70\x6d\x20": "jpm",
        "\x6d\x6a\x70\x32": "mj2",
        "\xFF\x4F\xFF\x51": "j2c",
    }
    trailer = "\xFF\xD9"
    cdata = data
    end = 0
    try:
        jtype = data[20:24]
        if jtype in ftyps:
            file_type = ftyps[jtype]
        else:
            return
        while True:
            findend = cdata.find(trailer)
            if findend == -1:
                return
            else:
                end += findend + 2
            # Another jp2 codestream
            if cdata[findend + 6 : findend + 10] == "jp2c":
                cdata = cdata[findend + 2 :]
            # Possible .mov file types
            elif file_type == "mj2" and cdata[findend + 6 : findend + 10] in [
                "free",
                "mdat",
                "moov",
                "pnot",
                "skip",
                "wide",
            ]:
                msize = struct.unpack(">I", cdata[findend + 2 : findend + 6])[0]
                jp2_data = data[0 : end + msize]
                break
            else:
                jp2_data = data[0:end]
                break
        return jp2_data
    except Exception:
        return


def find_additional_content(data):
    """Looks for appended file content attached to an image.

    Args:
        data: image content in bytes

    Returns:
        Embedded file data if found, or None.
    """
    PAT_FILEMARKERS = {
        # Header, Trailer, additional methods
        "bmp": (b"\x42\x4D", None, bmp_dump),
        "gif": (b"\x47\x49\x46\x38.\x61.{19,}\x2C.{9,}", b"\x00\x3B", None),
        "jpeg": (b"\xFF\xD8.{16,}\xFF\xDB.{3,}\xFF\xDA.{13,}", b"\xFF\xD9", None),
        "jpeg2000": (b"\x00\x00\x00\x0C\x6A\x50\x20\x20\x0D\x0A", None, jpg2_dump),
        "png": (b"\x89\x50\x4E\x47", b"\x49\x45\x4E\x44.{4}", None),
    }

    for _, tinfo in iter(PAT_FILEMARKERS.items()):
        # Build up the regex
        embed_regex = re.compile(tinfo[0] + b".+" + (tinfo[1] or b""), re.DOTALL)
        # Find the pattern that should match the image.
        img_match = re.match(embed_regex, data)
        if img_match:
            img_data = img_match.group()
            # Go to extraction module if there is one
            if tinfo[2] is not None:
                img_data = tinfo[2](img_data)

            # Otherwise extract data as-is (regex is considered good enough)
            leftovers = data.replace(img_data, b"")

            # Remove trailing NULL bytes
            leftovers = re.sub(b"[\x00]*$", b"", leftovers)

            if len(leftovers) > 15:
                # Recursively inspect the leftovers for more embedded content
                return leftovers
    return
