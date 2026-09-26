def get_total_number_of_sequences(*a):
    d = {}
    for x in a[0]:
        d[x] = d.get(x, 0) + 1
    return d



assert get_total_number_of_sequences(10, 4) == 4
assert get_total_number_of_sequences(5, 2) == 6
assert get_total_number_of_sequences(16, 3) == 84