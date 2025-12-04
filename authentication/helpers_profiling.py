import time

class LoginTimer:
    def __init__(self):
        self.start = None

    def begin(self):
        self.start = time.time()

    def end(self):
        if self.start is None:
            return 0
        return (time.time() - self.start) * 1000