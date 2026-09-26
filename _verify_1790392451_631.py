def odd_values_string(*a):
    return [x for x in a[0] if x % 2 == 1]



assert odd_values_string('abcdef') == 'ace'
assert odd_values_string('python') == 'pto'
assert odd_values_string('data') == 'dt'
assert odd_values_string('lambs') == 'lms'