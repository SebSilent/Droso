def get_total_number_of_sequences(dict, n):
    result = {key: value for key, value in dict.items() if value >= n}
    return result


assert get_total_number_of_sequences(10, 4) == 4
assert get_total_number_of_sequences(5, 2) == 6
assert get_total_number_of_sequences(16, 3) == 84