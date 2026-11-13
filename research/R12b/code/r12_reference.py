"""Compare historical R12 outcomes while permitting only R12b's two new counters."""
NEW_COUNTERS={'benign_combos_total','benign_combos_own'}

def assert_reference(current,reference,path='R12'):
    if isinstance(reference,dict):
        if not isinstance(current,dict) or set(reference)-set(current) or set(current)-set(reference)-NEW_COUNTERS:
            raise ValueError(f'Historical R12 schema mismatch: {path}')
        for key,value in reference.items():assert_reference(current[key],value,f'{path}/{key}')
    elif current!=reference:
        raise ValueError(f'Historical R12 outcome mismatch: {path}')

def check_rule_zero(current,baseline):
    for key in ('seed','K','attacker_site_pairs','scenarios','time_to_block','forged_blocks_per_hour','forged_total'):
        assert_reference(current[key],baseline[key],key)
    if set(current['sites'])!=set(baseline['sites']):raise ValueError('Historical R12 site population mismatch')
    for site in baseline['sites']:
        for field in ('windows','day0_fit_windows'):
            assert_reference(current['sites'][site][field],baseline['sites'][site][field],f'sites/{site}/{field}')
