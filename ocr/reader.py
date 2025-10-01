import easyocr
from threading import Lock

_reader = None
_lock = Lock()

def get_reader(langs=None, gpu=False):
    """
    Lazily create a single EasyOCR Reader for the process.
    langs: e.g. ['en'] or ['en','id']  (English + Indonesian)
    gpu:   False for CPU-only
    """
    global _reader
    if langs is None:
        langs = ['en']
    if _reader is None:
        with _lock:
            if _reader is None:
                _reader = easyocr.Reader(langs, gpu=gpu)
    return _reader