def odd_values_string(*a):
    out = []
    for x in a[0]:
        if x != 0:
            out.append(x)
    return out



assert odd_values_string('abcdef') == 'ace'
assert odd_values_string('python') == 'pto'
assert odd_values_string('data') == 'dt'
assert odd_values_string('lambs') == 'lms'