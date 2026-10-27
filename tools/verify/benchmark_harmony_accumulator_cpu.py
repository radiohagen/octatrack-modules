#!/usr/bin/env python3
"""Focused linked ha_fire_c boundary costs; host-only fixture setup is uncounted."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--integration',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--repeat',type=int,default=3)
    args=parser.parse_args()
    if args.repeat<=0:
        parser.error('--repeat must be positive')
    sys.path.insert(0,str(args.integration/'tools/verify'))
    from benchmark_harmony_cpu import CpuMachine
    machines=[CpuMachine(args.baseline),CpuMachine(args.candidate)]
    phase_sizes=[]
    for machine,path in zip(machines,(args.baseline,args.candidate)):
        rows=[line.split() for line in subprocess.check_output(
            ['m68k-elf-nm','-S',str(path/'platform/runtime/runtime.elf')],text=True).splitlines()]
        matches=[row for row in rows if len(row)==4 and row[2]=='b' and row[3]=='phases']
        assert len(matches)==1,matches
        address,size=int(matches[0][0],16),int(matches[0][1],16)
        assert machine.sym['phases']==address
        phase_sizes.append(size)
    assert phase_sizes[0]==phase_sizes[1]
    phase_size=phase_sizes[0]

    scenarios=('fresh_start_identity','established_start_new_pattern',
               'established_start_same_pattern','established_no_start_new_pattern',
               'established_steady')
    records={}
    for repeat in range(args.repeat):
        for scenario in scenarios:
            for policy in range(4):
                results=[]
                for machine in machines:
                    machine.c('ha_bank_reset_c',0)
                    machine.c('ha_runtime_reset_c')
                    for pattern in (0,1):
                        machine.uc.mem_write(machine.sym['ha_lanes']+pattern*8*37+32,
                                             bytes((0,7,0,policy,9)))
                    if scenario!='fresh_start_identity':
                        for _ in range(2):
                            machine.c('ha_fire_c',0,0,0,0)
                            machine.c('ha_sounded_c',0)
                    if scenario in ('fresh_start_identity','established_start_new_pattern',
                                    'established_start_same_pattern'):
                        machine.c('ha_transport_c')
                    pattern=1 if scenario in ('established_start_new_pattern',
                                               'established_no_start_new_pattern') else 0
                    lanes_before=bytes(machine.uc.mem_read(machine.sym['ha_lanes'],16*128*37))
                    def fire():
                        machine.c('ha_fire_c',0,pattern,0,0)
                        return bytes(machine.uc.mem_read(machine.sym['phases'],phase_size)).hex()
                    count,masked,digest,hotspots=machine.profile(fire)
                    assert lanes_before==bytes(machine.uc.mem_read(machine.sym['ha_lanes'],16*128*37))
                    shifted=machine.c('ha_shift_c',48,0,0)
                    expected=(48 if scenario=='fresh_start_identity' or
                              (scenario=='established_start_new_pattern' and policy) or
                              (scenario=='established_start_same_pattern' and policy&1) or
                              (scenario=='established_no_start_new_pattern' and policy&2) else 52)
                    assert shifted==expected,(scenario,policy,shifted,expected)
                    results.append((count,masked,digest,shifted,hotspots))
                assert results[0][2:4]==results[1][2:4],(scenario,policy,results)
                name=f'{scenario}/policy_{policy}'
                values={'baseline_instructions':results[0][0],
                        'candidate_instructions':results[1][0],
                        'instruction_delta':results[1][0]-results[0][0],
                        'reduction_percent':round(100*(1-results[1][0]/results[0][0]),2),
                        'baseline_max_masked':results[0][1],
                        'candidate_max_masked':results[1][1],
                        'result_sha256':results[0][2],
                        'shifted_note':results[0][3]}
                if repeat:
                    assert records[name]==values,('nondeterministic fixture',name,records[name],values)
                else:
                    records[name]=values
    args.out.mkdir(parents=True,exist_ok=True)
    regressions={name:value for name,value in records.items() if value['instruction_delta']>0}
    report={'passed':True,'measurement':'executed linked ColdFire instructions, not hardware cycles',
            'fixture_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'repeat':args.repeat,'phase_state_bytes_compared':phase_size,
            'baseline':str(args.baseline),'candidate':str(args.candidate),
            'artifact_sha256':{label:{name:hashlib.sha256((path/name).read_bytes()).hexdigest()
                                     for name in ('mainos_bus.bin','platform/runtime/runtime.elf','platform/runtime/runtime.bin')}
                               for label,path in (('baseline',args.baseline),('candidate',args.candidate))},
            'cases':records,'regressions':regressions,'hardware_tested':False}
    (args.out/'accumulator-boundaries-receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=[f'{name}: {row["baseline_instructions"]} -> {row["candidate_instructions"]} instructions '
           f'({row["instruction_delta"]:+d}); masked {row["baseline_max_masked"]} -> {row["candidate_max_masked"]}; '
           f'identical phase state, note {row["shifted_note"]}' for name,row in records.items()]
    lines.append(f'PASS: {len(records)} cases repeated {args.repeat} times; {len(regressions)} instruction regressions')
    (args.out/'accumulator-boundaries.log').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines),flush=True)


if __name__=='__main__':
    main()
