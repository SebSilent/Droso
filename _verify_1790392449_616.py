def odd_values_string(str):
    odd_values_string = 0
    for i in range(len(str)):
        if str[i] >= 'A' and str[i] <= 'Z':
            odd_values_string += 1
        return odd_values_string


assert odd_values_string('abcdef') == 'ace'
assert odd_values_string('python') == 'pto'
assert odd_values_string('data') == 'dt'
assert odd_values_string('lambs') == 'lms'