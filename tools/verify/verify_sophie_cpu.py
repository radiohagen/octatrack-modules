#!/usr/bin/env python3
"""Profile Sophie's linked ColdFire renderer with representative FUSE controls.

Counts executed instructions and long divisions, not hardware cycles. The
standalone link uses the checked-in adapter assembly and the same CPU model as
the Octabam runtime; it excludes the surrounding firmware and cache effects.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn.m68k_const import UC_CPU_M68K_CFV4E, UC_M68K_REG_A7, UC_M68K_REG_PC, UC_M68K_REG_SR

ROOT = Path(__file__).resolve().parents[2]


def output(command):
    return subprocess.check_output(command, text=True)


def profile(elf, scenario):
    symbols = {
        fields[-1]: int(fields[0], 16)
        for line in output(["m68k-elf-nm", "-S", str(elf)]).splitlines()
        if len(fields := line.split()) in (3, 4)
    }
    opcodes, owners = {}, {}
    owner = ""
    for line in output(["m68k-elf-objdump", "-d", str(elf)]).splitlines():
        if match := re.match(r"^([0-9a-f]+) <([^>]+)>:", line):
            owner = match[2]
        if match := re.match(
            r"^\s*([0-9a-f]+):\s+(?:[0-9a-f]{4}\s+)+\s*([a-z][a-z0-9.]+)", line
        ):
            address = int(match[1], 16)
            opcodes[address], owners[address] = match[2], owner

    with tempfile.TemporaryDirectory() as temporary:
        binary = Path(temporary) / "runtime.bin"
        subprocess.run(["m68k-elf-objcopy", "-O", "binary", str(elf), str(binary)], check=True)
        image = binary.read_bytes()
    assert len(image) < 0x10000
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(UC_CPU_M68K_CFV4E)
    uc.mem_map(0x10000, 0x10000)
    uc.mem_write(0x10000, image)
    uc.mem_map(0x20000, 0x10000)
    uc.mem_map(0x100b1000, 0x1000)
    uc.mem_map(0x80004000, 0x1000)
    uc.reg_write(UC_M68K_REG_SR, 0x2000)
    uc.mem_write(0x100b14f0, b"FMSYNTH-SOPHIE.wav\0")
    counts, functions = Counter(), Counter()

    def tick(_uc, address, _size, _user):
        counts[opcodes.get(address, "unknown")] += 1
        functions[owners.get(address, "unknown")] += 1

    uc.hook_add(UC_HOOK_CODE, tick)

    def call(name, *arguments):
        counts.clear()
        functions.clear()
        uc.reg_write(UC_M68K_REG_A7, 0x28000)
        uc.mem_write(
            0x28000,
            struct.pack(">" + "I" * (1 + len(arguments)), 0x20000, *arguments),
        )
        uc.emu_start(symbols[name], 0x20000, count=200000)
        assert uc.reg_read(UC_M68K_REG_PC) == 0x20000, name
        return {
            "instructions": sum(counts.values()),
            "multiplies": sum(value for key, value in counts.items() if key.startswith("mul")),
            "divides": sum(value for key, value in counts.items() if key.startswith(("div", "rem"))),
            "functions": dict(functions),
        }

    state = bytearray(128)
    struct.pack_into(">I", state, 12, scenario["pitch"])
    struct.pack_into(">I", state, 24, 32768)
    struct.pack_into(">H", state, 38, 32768)
    uc.mem_write(0x22000, bytes(state))
    controls = struct.pack(
        ">6H", 0x4000, scenario["color"] << 8, scenario["metal"] << 8,
        0x4000, scenario["feedback"] << 8, (scenario["sweep"] + 64) << 8,
    )
    uc.mem_write(0x23000, controls)
    for track in range(scenario["tracks"]):
        uc.mem_write(0x800049d8 + 0xa8 * track + 8, struct.pack(">I", 0x100b14f0))
        call("sf_begin", track)
    calls = []
    for _ in range(24):
        for track in range(scenario["tracks"]):
            calls.append(call("sf_fill", track, 0x22000, 0x23000, 0x24000, 16))
    warm = calls[8 * scenario["tracks"]:]
    count = len(warm)
    return {
        "cold": calls[:scenario["tracks"]],
        "warm_per_16_frames": {
            field: sum(item[field] for item in warm) / 16
            for field in ("instructions", "multiplies", "divides")
        },
        "warm_by_function": {
            name: sum(item["functions"].get(name, 0) for item in warm) / 16
            for name in sorted({name for item in warm for name in item["functions"]})
        },
        "calls": count,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, help="Profile an existing standalone linked adapter")
    parser.add_argument("--output", type=Path, default=ROOT / "out/sophie-cpu.json")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        if args.elf:
            elf = args.elf
        else:
            obj = Path(temporary) / "adapter.o"
            elf = Path(temporary) / "adapter.elf"
            subprocess.run(
                ["m68k-elf-as", "-mcpu=54455", "-o", str(obj),
                 str(ROOT / "modules/sophie/adapter.s")], check=True
            )
            subprocess.run(
                ["m68k-elf-gcc", "-mcpu=54455", "-nostdlib", "-Wl,-Ttext=0x10000",
                 "-Wl,-e,sf_fill", str(obj), "-lgcc", "-o", str(elf)], check=True
            )
        scenarios = {
            "plain": dict(pitch=25480119, color=50, metal=0, feedback=0, sweep=0, tracks=1),
            "metallic": dict(pitch=25480119, color=50, metal=80, feedback=48, sweep=0, tracks=1),
            "sweep": dict(pitch=25480119, color=50, metal=80, feedback=48, sweep=63, tracks=1),
            "two_tracks": dict(pitch=25480119, color=50, metal=80, feedback=48, sweep=0, tracks=2),
        }
        receipt = {
            "adapter_sha256": None if args.elf else hashlib.sha256(
                (ROOT / "modules/sophie/adapter.s").read_bytes()
            ).hexdigest(),
            "profiled_elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
            "hardware_cycles": False,
            "samples_per_call": 16,
            "scenarios": {name: profile(elf, case) for name, case in scenarios.items()},
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    for name, case in receipt["scenarios"].items():
        print(name, case["warm_per_16_frames"])
    print("receipt", args.output)


if __name__ == "__main__":
    main()
