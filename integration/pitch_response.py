"""Build-time binding for one optional MIDI pitch owner.

These synchronous requests return values; they are not EVENTS notifications.
No provider emits no flag, macro body, table or runtime lookup. A selected
provider owns the musical policy and may not emit MIDI or change native note
ownership. Preparation may synchronize its captured root event; the remaining
requests are read-only and never advance an arp/generator/history.

All callbacks preserve SP, the interrupt mask and registers except their
documented results. Condition codes are not results.

capture: d0 track -> d0 0/1, whether an arp-only tick keeps its published root.
prepare: d0 raw NOTE, d1 stock scale rotation, d7 source -> prepared d0/d1.
owned:   d0 track -> d0 0/1, whether generated voices belong to the provider.
quant:   d0 pitch, d1 track -> d0 normalized pitch.
target:  d0 followed root after native TRAN, d1 receiver -> d0 effective root.
shift:   d0 voice, d1 old root, d2 new root, d7 receiver -> d0 voice;
         256 declines to native policy, -1 suppresses an invalid voice.

Shift requires owned(track) to have returned 1 for this same receiver response
operation. The caller may reuse that decision for its four voices, but must
not retain it across service calls, receivers, mode edits or context changes.
The provider therefore need not repeat its ownership lookup for every voice.
"""
import re


CALLBACKS = ('capture', 'prepare', 'owned', 'quant', 'target', 'shift')
PROVIDERS = (('MIDI HARMONY', 'mh_pitch'),)


def pitch_inc(modules, remix=None):
    """Generate direct calls using the existing Linked.include contract."""
    keys, prefixes, selected = set(), set(), []
    for key, prefix in PROVIDERS:
        if (not key or key in keys or prefix in prefixes
                or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', prefix)):
            raise ValueError(f'invalid MIDI pitch provider: {key!r}, {prefix!r}')
        keys.add(key)
        prefixes.add(prefix)
        if key in modules:
            selected.append(prefix)
    if len(selected) > 1:
        raise ValueError('MIDI pitch response permits only one selected provider')
    if not selected:
        return ''
    out = ['.set HAVE_PITCH_RESPONSE,1']
    for callback in CALLBACKS:
        out += [f'.macro pitch_{callback}',
                f'    jsr {selected[0]}_{callback}', '.endm']
    return '\n'.join(out) + '\n'
