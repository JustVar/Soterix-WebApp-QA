# H.265 in Chrome on Linux

The QA server streams H.265. Chrome on Linux has no software decoder for it.
It decodes H.265 only through the GPU's VA-API decoder, and only from its
Wayland backend. Without this recipe, the tests marked `livestream` skip on
Linux and the stream guard says why. Windows and Mac Chrome need no setup.

This recipe ran on one Linux machine with an Intel GPU until 09/2026. That
machine is offline, so nothing here has been proven since. Do the decode
check at the end before you trust it.

## Packages

1. `grep -l 0x8086 /sys/class/drm/renderD*/device/vendor` must print a path.
   If it prints nothing, enable the CPU graphics in the BIOS.
2. `sudo apt-get install intel-media-va-driver vainfo weston`.
3. `vainfo` on the Intel render node must list `VAProfileHEVCMain`.
4. Add the test user to the groups `video` and `render`.
5. Install Google Chrome from Google's apt repository, not Playwright's
   Chromium. `pytest.ini` sets `--browser-channel chrome`.

## The Weston display

A test machine has no monitor, so Weston gives Chrome its Wayland display.
Run it as a systemd service as the test user:

```
ExecStart=/usr/bin/weston --backend=headless --renderer=gl --socket=wl-qa --idle-time=0 --width=1600 --height=900
RuntimeDirectory=qa-weston
Environment=XDG_RUNTIME_DIR=/run/qa-weston
Environment=__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
```

`--idle-time=0` keeps the output on. The EGL line makes Mesa pick the Intel
render node, not another GPU. After `systemctl enable --now`, the journal
must name the Intel GPU on its `GL renderer` line.

## The 4 settings for a run

- `XDG_RUNTIME_DIR=/run/qa-weston` and `WAYLAND_DISPLAY=wl-qa` name the
  Weston socket.
- `--headed`. Headless Chrome ignores the Wayland flag and loses the GPU
  process on the first decoded frame.
- `CHROME_ARGS="--ozone-platform=wayland"`. Without it Chrome selects X11
  and does not start on a machine with no X server.

No other flag is necessary. A comparison of this 1 flag with a set of 8 on
the real tests gave identical results. The session, the stream guard and
`tools/stream_probe.py` read the same `CHROME_ARGS`, so the guard measures
the browser the tests get.

## The decode check

```
XDG_RUNTIME_DIR=/run/qa-weston WAYLAND_DISPLAY=wl-qa CHROME_ARGS=--ozone-platform=wayland \
  venv/bin/python -c "from tests.shared.helpers.stream_health import decode_check; print(decode_check('H.265', 'chrome', headed=True))"
```

The output must show `'decodes': True` and a browser name that contains
`headed`. In a run, the `[STREAM]` line in the terminal summary ends with
`decodes H.265: yes`.

## Approaches that failed

Each one was measured. Do not try them again.

- Every backend that is not Wayland (headless, Xvfb, X11) loses the GPU
  process with `Could not find SharedImageBackingFactory ... BGRA_8888`.
  GPU memory buffers, zero copy, no compositing and the legacy decoder did
  not change that.
- Under Xvfb or headless, Chrome opens the first render node it finds and
  does not call libva unless you pin the node.
- An NVIDIA GPU with `nvidia-vaapi-driver` reached readyState 1, then gave
  `PIPELINE_ERROR_DECODE`.
- `--ozone-platform=drm` is not in Google Chrome's build.
