#!/usr/bin/env python3
"""POST FADER on the current firmware and DSPs, adapted from PR 542.

Stages owned copies with muted T7's sends at 100 or 0, then repeats with
T2 soloed (T7 excluded). Compares both bus hosts after warm-up; matching
returns prove the excluded sender neither feeds nor dilutes either bus.
A negative control restores the stock builder call in a private image:
the same muted-track send change must then affect both returns. The
installed-hook gate separately covers every level, records and registers.

Does not establish physical timing, instantaneous mute, or crossfader XLV.
Existing effect state is retained; SEND's normal smoothing remains.
"""
import argparse, contextlib, os, pathlib, re, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); import toolpath  # noqa: E402,F401
from remix import registry  # noqa: E402
import ot_project as otp  # noqa: E402
import blockdump as bd  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMU = ROOT / "out/emu/ot_emu"
PY = ROOT / ".venv/bin/python3"
OUT = ROOT / "out/postfaderverify"
FRAMES, WARM = 1000, 650              # both engines warm up dry after load
FIXTURES = (("t7on", 100), ("t7off", 0), ("soloon", 100), ("solooff", 0),
            ("stockon", 100), ("stockoff", 0))
RETURNS_RB = ((1, (0x80003190, 0x80003590), 0, "T1"), (0, (0x80003390, 0x80003790), 0, "T5"))


def stage(template, remix, tag, t7, audio):
    d = OUT / tag
    shutil.rmtree(d, ignore_errors=True)
    (d / "project").mkdir(parents=True)
    for f in template.iterdir():
        if f.is_file() and f.suffix.lower() in (".work", ".strd"):
            shutil.copy2(f, d / "project" / f.name)
    p = d / "project"
    otp.host_rig(p, remix, guard=False)
    otp.set_fx(p, "fx2", 8, "DELAY", guard=False)          # the hosts print: no RETURNS
    otp.stamp_slot(p, "SEND", "DEL", 100, guard=False)
    otp.stamp_slot(p, "SEND", "REV", 100, guard=False)
    otp.stamp_slot(p, "SEND", "DEL", t7, guard=False, tracks={7})
    otp.stamp_slot(p, "SEND", "REV", t7, guard=False, tracks={7})

    def free(data):
        # locks on FX2 slots 0-1 (lock slots 24, 25) and LFOs on them would
        # move the knobs the records are checked against
        for pat in range(16):
            for t in range(8):
                base = otp.trac_off(pat, t) + 0x59
                for st in range(64):
                    data[base + st * 32 + 24] = 0xff
                    data[base + st * 32 + 25] = 0xff
        for part in range(otp.NPARTS_ALL):
            for t in range(8):
                lfo = otp.PART_BASE + part * otp.PART_STRIDE + otp.LFO_PM_OFF + t * 30
                for k in range(3):
                    if data[lfo + k] in (24, 25):
                        data[lfo + k] = 18
    for bw in sorted(p.glob("bank*.work")):
        otp._bank_write(p, int(bw.name[4:6]), free, guard=False)
    raw = (p / "project.work").read_bytes().replace(b"MASTER_TRACK=1", b"MASTER_TRACK=0")
    # Own the mute state; do not rely on an arbitrary user's template.
    raw, nm = re.subn(rb"(?m)^TRACK_MUTE_MASK=\d+", (b"TRACK_MUTE_MASK=0" if tag.startswith("solo") else b"TRACK_MUTE_MASK=64"), raw)
    raw, ns = re.subn(rb"(?m)^TRACK_SOLO_MASK=\d+", (b"TRACK_SOLO_MASK=2" if tag.startswith("solo") else b"TRACK_SOLO_MASK=0"), raw)
    assert nm == ns == 1, "fixture must contain audio mute/solo masks"
    (p / "project.work").write_bytes(re.sub(rb"\r\nPATTERN=\d+\r\n", b"\r\nPATTERN=0\r\n", raw))
    cmd = [str(PY), str(ROOT / "tools/emu/ot_emu/stage_card.py"), str(p), "OCTABAM", "PF",
           "--tree", str(d / "tree"), "--out", str(d / "card.img"), "--image-mb", "64"]
    for a in audio:
        cmd += ["--audio", a]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"verify_postfader: stage_card {tag} failed:\n{r.stdout[-800:]}{r.stderr[-800:]}")


def run(image, tag):
    d = OUT / tag
    cmd = [str(EMU), "--image", str(image), "--card", str(d / "card.img"), "--set", "OCTABAM",
           "--project", "PF", "--sequencer", "--internal-clock", "--frames", str(FRAMES),
           "--load-ms", "90000", "--dsp", "--main-level", "64",
           "--block-dump", str(d / "blocks.dump"),
           "--mem-dump", f"0x80000000,0x8000={d / 'sram.bin'}"]
    with open(d / "run.txt", "w") as f:
        r = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    return tag, r.returncode


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("remix", nargs="?", default=os.environ.get("REMIX"))
    ap.add_argument("--project", default=os.environ.get("OT_PROJECT", ""))
    ap.add_argument("--image", default="")
    a = ap.parse_args()
    remix = registry.remix(a.remix)
    if "POST FADER" not in remix.modules:
        print(f"  [ -- ] verify_postfader: {a.remix} carries no POST FADER"); return 0
    if not a.project:
        print("  [SKIP] verify_postfader: no project (OT_PROJECT=<dir> or --project)"); return 0
    if not EMU.is_file():
        print("  [SKIP] verify_postfader: no port binary (make emu-cf)"); return 0
    template = pathlib.Path(a.project).expanduser()
    if not (template / "project.work").is_file():
        sys.exit(f"verify_postfader: {template} is not a project")
    OUT.mkdir(parents=True, exist_ok=True)
    image = OUT / "mainos.bin"
    if a.image:
        source = pathlib.Path(a.image).resolve()
        if source != image.resolve():
            shutil.copy2(source, image)
    else:
        env = dict(os.environ, REMIX=a.remix, XBUS="1", SPEC="1"); env.setdefault("BUILD", "0")
        r = subprocess.run([sys.executable, str(ROOT / "tools/build/build_bus.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            sys.exit(f"verify_postfader: building {a.remix} failed:\n{(r.stdout + r.stderr)[-1500:]}")
        shutil.copy2(ROOT / "out/mainos_bus.bin", image)
    audio = []
    for s in otp.read_project(template)[1]:
        rel = s["path"]
        src = (template / rel).resolve() if rel else None
        if src is not None and src.is_file():
            audio.append(f"{src}:{rel[3:] if rel.startswith('../') else 'PF/' + rel}")
    # Restore only this module's hook for a causally useful negative control.
    control = bytearray(image.read_bytes())
    control[0x4000d0e4 - 0x40000400:0x4000d0ea - 0x40000400] = bytes.fromhex("4eb940004bd4")
    stock = OUT / "without-postfader.bin"
    stock.write_bytes(control)
    for tag, t7 in FIXTURES:
        with open(os.devnull, "w") as quiet, contextlib.redirect_stdout(quiet):
            stage(template, a.remix, tag, t7, sorted(set(audio)))
        print(f"  staged {tag}", flush=True)
    with ThreadPoolExecutor(2) as ex:
        codes = dict(ex.map(lambda f: run(stock if f[0].startswith("stock") else image, f[0]), FIXTURES))

    fails = 0

    def check(msg, ok):
        nonlocal fails
        print(f"  [{'ok' if ok else 'FAIL'}] {msg}")
        fails += not ok

    for tag, code in codes.items():
        check(f"{tag}: {FRAMES} frames ran (exit {code})", code == 0)
    if fails:
        print(f"verify_postfader: FAIL ({fails})"); return 1

    mods = registry.modules()
    send_id, dly_id = mods["SEND"].menu.fx2_id, mods["DELAY SERVER"].menu.fx2_id
    d = (OUT / "t7on" / "sram.bin").read_bytes()
    u16 = lambda addr: int.from_bytes(d[addr - 0x80000000:addr - 0x80000000 + 2], "big")
    u32 = lambda addr: int.from_bytes(d[addr - 0x80000000:addr - 0x80000000 + 4], "big")
    rec = 0x80000110 + (u32(0x800000e0) << 9)
    mix = u32(0x80003c10)
    for t in range(8):
        fid = u16(rec + 64 * t + 56)
        lvl = u16(mix + 8 * t + 2) >> 8
        s0, s1 = u16(rec + 64 * t + 24), u16(rec + 64 * t + 26)
        if fid in (send_id, 0):
            want = (100 << 8) * lvl * lvl >> 14
            check(f"T{t + 1} SEND at L {lvl}: DEL/REV {s0:04x}/{s1:04x}, want {want:04x}"
                  + (" (muted: 0)" if lvl == 0 else ""), s0 == want and s1 == want)
        elif t == 7:
            check(f"T8 (FX2 id {fid:#x}, not a send) keeps its knobs ({s0:04x}/{s1:04x})",
                  fid not in (send_id, 0, dly_id))
    check("T7 is muted in the fixture (its MAIN gain reads 0)", u16(mix + 8 * 6 + 2) == 0)

    for left, right, equal in (("t7on", "t7off", True), ("soloon", "solooff", True),
                               ("stockon", "stockoff", False)):
        A = bd.classes(bd.read(OUT / left / "blocks.dump"))
        B = bd.classes(bd.read(OUT / right / "blocks.dump"))
        for core, rams, ti, name in RETURNS_RB:
            n = k = nonzero = 0
            for ram in rams:
                sa = {f: w for f, w in A.get(('<', 1, core, ram), [])}
                sb = {f: w for f, w in B.get(('<', 1, core, ram), [])}
                for f in sa.keys() & sb.keys():
                    if f > WARM:
                        n += 1
                        x, y = sa[f][64 * ti:64 * ti + 64], sb[f][64 * ti:64 * ti + 64]
                        k += x != y
                        nonzero += any(x) or any(y)
            check(f"{left}/{right}: {name} {'identical' if equal else 'DIFFERS without hook'} "
                  f"({k}/{n} frames differ; {nonzero} non-silent)",
                  n > 100 and nonzero > 100 and ((k == 0) if equal else (k > 0)))
    solo = (OUT / "soloon" / "sram.bin").read_bytes()
    mix = int.from_bytes(solo[0x3c10:0x3c14], "big") - 0x80000000
    check("solo fixture keeps T2 audible and zeros T7 MAIN gain",
          int.from_bytes(solo[mix+10:mix+12], "big") > 0
          and solo[mix+50:mix+52] == bytes(2))
    print(f"verify_postfader: {'ok' if not fails else 'FAIL'} ({fails} failure(s))")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
