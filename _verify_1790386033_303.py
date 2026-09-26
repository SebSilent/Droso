def odd_values_string(str1):
    str2 = ''
    for i in range(1, len(str1) + 1):
        if i % 2 == 0:
            str2 = str2 + str1[i - 1]
    return str2


assert odd_values_string('abcdef') == 'ace'
assert odd_values_string('python') == 'pto'
assert odd_values_string('data') == 'dt'
assert odd_values_string('lambs') == 'lms'