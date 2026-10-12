#!/usr/bin/env python3
"""
Headless test harness for VICE (x64sc, xplus4, x128, xvic, xpet...).

It drives the emulator through VICE's *binary monitor* (a TCP remote-control
protocol built into VICE 3.5+), so the unmodified release binary can be tested:

  * stop the machine once per video frame (checkpoint on a code address),
  * script the controls frame by frame (the harness overwrites the byte where
    the program has just stored its decoded input; VICE 3.7's own joystick
    injection is not usable: it does not reach the emulated ports headless
    and it is applied with a random delay),
  * read or write memory (state traces, cheats, data injection),
  * grab the emulated screen as a PNG.

Everything runs in warp mode with no sound, so runs are fast and, because the
input is applied at exact frame boundaries, fully repeatable.

Requirements: VICE 3.5 or newer, python3 + Pillow. With no X display available
(e.g. over ssh) it uses xvfb-run automatically if it is installed.

Typical use (see platforms/c64/tests/ for complete scenarios):

    from vice_harness import Vice, load_labels
    lab = load_labels("build/jumpingjim.lbl")
    with Vice("build/jumpingjim.prg", video="pal") as v:
        v.start(lab["irq_top"], lab["ri_end"], lab["input"])
        for frame in range(500):
            v.set_input(8 if frame == 300 else 0)    # 8 = fire in this game
            v.next_frame()
        v.screenshot().save("shot.png")
"""
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time

from PIL import Image

STX, API = 0x02, 0x02
EVENT_ID = 0xFFFFFFFF

# binary monitor commands
C_MEM_GET, C_MEM_SET = 0x01, 0x02
C_CHECK_SET, C_CHECK_DEL = 0x12, 0x13
C_REG_GET = 0x31
C_BANKS, C_DISPLAY, C_PALETTE = 0x82, 0x84, 0x91
C_EXIT, C_QUIT, C_AUTOSTART = 0xAA, 0xBB, 0xDD
# responses / events
R_CHECK, R_STOPPED, R_RESUMED, R_JAM = 0x11, 0x62, 0x63, 0x61


def load_labels(path):
    """Read a VICE label file (acme --vicelabels) -> {name: address}."""
    labels = {}
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) == 3 and parts[0] == "al":
                labels[parts[2].lstrip(".")] = int(parts[1].split(":")[-1], 16)
    return labels


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class ViceError(RuntimeError):
    pass


class Vice:
    def __init__(self, program=None, emulator="x64sc", video="pal", args=(),
                 timeout=60):
        """Start the emulator. `program` is autostarted (.prg, .d64, ...).
        `video` is 'pal', 'ntsc', 'ntscold' or 'paln'."""
        self.port = _free_port()
        self.timeout = timeout
        self.req = 0
        self.frame = -1
        self.frame_addr = None
        self.input_addr = None
        self.input_var = None
        self.input_value = 0
        self.hooks = {}
        self.ram_bank = 0
        self._palette = None
        self.logfile = tempfile.NamedTemporaryFile(
            prefix="vice-", suffix=".log", delete=False)
        cmd = [emulator, "-default", "-silent", "-sounddev", "dummy", "-warp",
               "-" + video,
               # VICE randomises the RAM contents and the autostart delay by
               # default; both must be off for repeatable runs
               "-raminitrandomchance", "0", "+autostart-delay-random",
               "-binarymonitor",
               "-binarymonitoraddress", "ip4://127.0.0.1:%d" % self.port]
        cmd += list(args)
        if program and program.lower().endswith(".prg"):
            # .prg files are injected straight into RAM; disk images are
            # attached to drive 8 and loaded like on the real machine
            cmd += ["-autostartprgmode", "1"]
        self.program = program
        if not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
            cmd = ["xvfb-run", "-a"] + cmd
        self.proc = subprocess.Popen(cmd, stdout=self.logfile,
                                     stderr=subprocess.STDOUT)
        self.sock = None
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise ViceError("emulator exited at start-up, see %s"
                                % self.logfile.name)
            try:
                self.sock = socket.create_connection(
                    ("127.0.0.1", self.port), timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        if not self.sock:
            raise ViceError("cannot connect to the VICE binary monitor")
        self.sock.settimeout(timeout)
        self.buf = b""
        # the first command stops the machine; find the RAM bank on the way
        for bank_id, name in self.banks():
            if name == "ram":
                self.ram_bank = bank_id

    # ------------------------------------------------------------ protocol
    def _send(self, command, body=b""):
        self.req += 1
        self.sock.sendall(struct.pack("<BBIIB", STX, API, len(body),
                                      self.req, command) + body)
        return self.req

    def _recv_exact(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ViceError("connection closed by VICE")
            self.buf += chunk
        data, self.buf = self.buf[:n], self.buf[n:]
        return data

    def _recv(self):
        stx, api, length, rtype, err, rid = struct.unpack(
            "<BBIBBI", self._recv_exact(12))
        if stx != STX:
            raise ViceError("protocol out of sync")
        return rtype, err, rid, self._recv_exact(length)

    def _command(self, command, body=b""):
        """Send a command and return the body of its reply."""
        rid = self._send(command, body)
        while True:
            rtype, err, got, data = self._recv()
            if got == rid:
                if err:
                    raise ViceError("command %02x failed, error %02x"
                                    % (command, err))
                return data
            if rtype == R_JAM:
                raise ViceError("CPU jam (the program crashed)")

    def _wait_event(self, wanted):
        while True:
            rtype, err, rid, data = self._recv()
            if rtype == R_JAM:
                raise ViceError("CPU jam (the program crashed)")
            if rtype == wanted:
                return data

    # ------------------------------------------------------------- control
    def banks(self):
        data = self._command(C_BANKS)
        count, pos, out = struct.unpack_from("<H", data)[0], 2, []
        for _ in range(count):
            size, bank_id, nlen = struct.unpack_from("<BHB", data, pos)
            name = data[pos + 4:pos + 4 + nlen].decode()
            out.append((bank_id, name))
            pos += 1 + size
        return out

    def checkpoint(self, addr, stop=True, op=4):
        """Exec (op=4), load (1) or store (2) checkpoint. Returns its number."""
        data = self._command(C_CHECK_SET, struct.pack(
            "<HHBBBB", addr, addr, int(stop), 1, op, 0))
        return struct.unpack_from("<I", data)[0]

    def delete_checkpoint(self, number):
        self._command(C_CHECK_DEL, struct.pack("<I", number))

    def resume(self):
        self._command(C_EXIT)

    def run_until_stop(self):
        """Resume and block until the next checkpoint stops the machine.
        Returns the program counter."""
        self.resume()
        return struct.unpack_from("<H", self._wait_event(R_STOPPED))[0]

    def start(self, frame_addr, input_addr=None, input_var=None):
        """Load and run the program given to the constructor.

        frame_addr: an address executed exactly once per video frame (the
                    top-of-frame interrupt); it is the clock of the test.
        input_addr: address reached right after the program has stored its
                    decoded controls in the byte `input_var`. The harness
                    overwrites that byte there with the scripted value (see
                    set_input), which makes the input exact to the frame.

        The checkpoints are set while the machine is still idle, so frame 0
        is always the first frame of the program and runs are repeatable."""
        self.frame_addr, self.input_addr = frame_addr, input_addr
        self.input_var = input_var
        self.checkpoint(frame_addr)
        if input_addr is not None:
            self.checkpoint(input_addr)
        name = os.path.abspath(self.program).encode()
        self._command(C_AUTOSTART, struct.pack("<BHB", 1, 0, len(name)) + name)

    def on(self, addr, callback):
        """Call callback(vice) every time the program reaches addr (the machine
        is stopped meanwhile, so the callback may read and write memory)."""
        self.checkpoint(addr)
        self.hooks[addr] = callback

    def set_input(self, value):
        """Scripted controls, held until changed (meaning is program specific)."""
        self.input_value = value

    def next_frame(self, n=1):
        """Advance n video frames (the machine stays stopped on return)."""
        for _ in range(n):
            while True:
                pc = self.run_until_stop()
                if pc == self.input_addr:
                    self.poke(self.input_var, self.input_value)
                elif pc in self.hooks:
                    self.hooks[pc](self)
                elif pc == self.frame_addr:
                    break
            self.frame += 1
        return self.frame

    # -------------------------------------------------------------- memory
    def peek(self, start, length=1, bank=None):
        bank = self.ram_bank if bank is None else bank
        data = self._command(C_MEM_GET, struct.pack(
            "<BHHBH", 0, start, start + length - 1, 0, bank))
        n = struct.unpack_from("<H", data)[0]
        return data[2:2 + n]

    def poke(self, start, values, bank=None):
        bank = self.ram_bank if bank is None else bank
        values = bytes([values]) if isinstance(values, int) else bytes(values)
        self._command(C_MEM_SET, struct.pack(
            "<BHHBH", 0, start, start + len(values) - 1, 0, bank) + values)

    def registers(self):
        data = self._command(C_REG_GET, b"\x00")
        count, pos, out = struct.unpack_from("<H", data)[0], 2, {}
        for _ in range(count):
            size, reg_id, value = struct.unpack_from("<BBH", data, pos)
            out[reg_id] = value
            pos += 1 + size
        return out

    # --------------------------------------------------------------- video
    def palette(self):
        if self._palette is None:
            data = self._command(C_PALETTE, b"\x01")
            count, pos, pal = struct.unpack_from("<H", data)[0], 2, []
            for _ in range(count):
                size = data[pos]
                pal += list(data[pos + 1:pos + 4])
                pos += 1 + size
            self._palette = pal
        return self._palette

    def screenshot(self, border=True):
        """Current emulated screen as a PIL image (palette mode).
        border=False crops to the 320x200 text/bitmap area."""
        data = self._command(C_DISPLAY, b"\x01\x00")
        hlen = struct.unpack_from("<I", data)[0]
        dw, dh, xo, yo, iw, ih, bpp = struct.unpack_from("<HHHHHHB", data, 4)
        blen = struct.unpack_from("<I", data, 4 + hlen)[0]
        pix = data[8 + hlen:8 + hlen + blen]
        # VICE 3.7 sends the buffer a few bytes short: pad the last line
        pix += bytes(dw * dh - len(pix))
        img = Image.frombytes("P", (dw, dh), pix)
        img.putpalette(self.palette())
        # (xo, yo, iw, ih) is the 320x200 text/bitmap area inside the raster
        if border:
            mx = min(32, xo, dw - xo - iw)
            my = min(36, yo - 8, dh - yo - ih)     # PAL 36 lines, NTSC 23
        else:
            mx = my = 0
        return img.crop((xo - mx, yo - my, xo + iw + mx, yo + ih + my))

    # ------------------------------------------------------------ shutdown
    def close(self):
        try:
            if self.sock:
                self._send(C_QUIT)
                self.sock.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.logfile.close()
        try:
            os.unlink(self.logfile.name)
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def contact_sheet(images, columns=4, scale=1, gap=4, bg=(32, 32, 32)):
    """Paste a list of same-sized images into one grid image."""
    images = [im.convert("RGB") for im in images]
    w, h = images[0].size
    w, h = w * scale, h * scale
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * (w + gap) + gap,
                              rows * (h + gap) + gap), bg)
    for i, im in enumerate(images):
        if scale != 1:
            im = im.resize((w, h), Image.NEAREST)
        sheet.paste(im, (gap + (i % columns) * (w + gap),
                         gap + (i // columns) * (h + gap)))
    return sheet


def save_gif(images, path, frame_ms=40, scale=1):
    """Write a list of images as an animated GIF."""
    frames = [im.convert("RGB") for im in images]
    if scale != 1:
        frames = [f.resize((f.width * scale, f.height * scale), Image.NEAREST)
                  for f in frames]
    frames = [f.quantize(colors=32, method=Image.MEDIANCUT, dither=Image.NONE)
              for f in frames]
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=frame_ms, loop=0, optimize=False)
