"""Local OCR child: length-prefixed input/output. No Discord or network access."""
import contextlib
import io
import os
import struct
import sys
from utils.scam_visual import near_copy
from utils.scam_rules import (normalize, classify_image_text, CELEBRITY, CASINO,
                              PROMO_CODE, REWARD, CLAIM, FIRST_PERSON, DOMAIN,
                              WITHDRAW, WALLET, report_context)

NEAR_MATCH = object()

MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 12_000_000
MAX_EDGE = 1600
MAX_OUTPUT = 24000
ENGINE = None


def read_text(im):
    buf = io.BytesIO()
    im.save(buf, format='PNG')
    rows, _ = ENGINE(buf.getvalue(), use_cls=False)
    return '\n'.join(str(row[1]) for row in (rows or []) if len(row) >= 3 and float(row[2]) >= 0.45)[:MAX_OUTPUT]


def retry_needed(text, width, height):
    # One additional pass at most. No extra work on ordinary images unless
    # the first pass found campaign-related signals.
    t = normalize(text)
    if classify_image_text(t) or report_context(t):
        return False
    if CELEBRITY.search(t) and (height > width or CASINO.search(t) or PROMO_CODE.search(t) or FIRST_PERSON.search(t)):
        return True
    if CASINO.search(t) and sum(bool(p.search(t)) for p in (PROMO_CODE, REWARD, CLAIM, FIRST_PERSON)) >= 2:
        return True
    if DOMAIN.search(t) and (WITHDRAW.search(t) or WALLET.search(t) or PROMO_CODE.search(t) or 'bonuses' in t):
        return True
    # Some support screenshots have the casino UI but the first OCR pass
    # misses the address bar. Retry only when several UI cues agree. These
    # cues alone never qualify an image for deletion.
    bonus_ui = sum(cue in t for cue in ('activate code for bonus', 'rakeback', 'vip-club', 'active bonuses', 'promo code'))
    payout_ui = sum(cue in t for cue in ('select a withdraw method', 'enter wallet address', 'withdrawal success', 'specified wallet', 'enter withdrawal amount'))
    return bonus_ui >= 3 or (payout_ui >= 3 and bool(WALLET.search(t)))


def enhanced_view(im):
    from PIL import Image, ImageOps
    # Keep the whole image, so the name and ad can both be recovered.
    # Autocontrast and bounded enlargement improve small, dim text.
    view = ImageOps.autocontrast(im.convert('L'), cutoff=1)
    if max(view.size) < MAX_EDGE:
        scale = min(2.0, MAX_EDGE / max(view.size))
        view = view.resize(tuple(max(1, round(d * scale)) for d in view.size), Image.Resampling.LANCZOS)
    return view.convert('RGB')


def extract(data):
    global ENGINE
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(data)) as im:
        if im.format not in {'PNG', 'JPEG', 'WEBP', 'BMP'} or im.width * im.height > MAX_PIXELS or getattr(im, 'n_frames', 1) != 1:
            return ''
        im = ImageOps.exif_transpose(im).convert('RGB')
        if near_copy(im):
            return NEAR_MATCH
        im.thumbnail((MAX_EDGE, MAX_EDGE))
    if ENGINE is None:
        import cv2
        cv2.setNumThreads(1)
        from rapidocr_onnxruntime import RapidOCR
        ENGINE = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
    first = read_text(im)
    if not retry_needed(first, im.width, im.height):
        return first
    second = read_text(enhanced_view(im))
    # Combine only observations from the SAME image. Put a newline between
    # passes and keep existing evidence requirements in the classifier.
    return (first[:MAX_OUTPUT // 2] + '\n' + second[:MAX_OUTPUT // 2])[:MAX_OUTPUT]


def main():
    source = sys.stdin.buffer
    # Keep the protocol on a duplicate fd, redirect native-library stdout too.
    sink = os.fdopen(os.dup(sys.stdout.fileno()), 'wb')
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    if hasattr(os, 'nice'):
        try: os.nice(10)
        except OSError: pass
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    # Do not let Python library diagnostics corrupt the protocol.
    with contextlib.redirect_stdout(sys.stderr):
        while True:
            header = source.read(4)
            if not header:
                return
            if len(header) != 4:
                return
            n = struct.unpack('!I', header)[0]
            if not 0 < n <= MAX_BYTES:
                return
            data = source.read(n)
            if len(data) != n:
                return
            try:
                result = extract(data)
                out = b'\x02' if result is NEAR_MATCH else b'\x00' + result.encode('utf-8')[:MAX_OUTPUT]
            except Exception as exc:
                # Error type only: don't leak image data or user text into logs.
                out = b'\x01' + type(exc).__name__.encode('ascii', 'replace')[:128]
            sink.write(struct.pack('!I', len(out)) + out)
            sink.flush()

if __name__ == '__main__':
    main()
