def get_total_number_of_sequences(*a):
    out = []
    for x in a[0]:
        if x == a[1]:
            out.append(x)
    return out



assert get_total_number_of_sequences(10, 4) == 4
assert get_total_number_of_sequences(5, 2) == 6
assert get_total_number_of_sequences(16, 3) == 84