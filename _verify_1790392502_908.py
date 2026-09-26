def string_to_tuple(str1):
    result = tuple(x for x in str1 if not x.isspace()) 
    return result


assert odd_values_string('abcdef') == 'ace'
assert odd_values_string('python') == 'pto'
assert odd_values_string('data') == 'dt'
assert odd_values_string('lambs') == 'lms'