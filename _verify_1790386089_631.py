def set_left_most_unset_bit(*a):
    return [x * x for x in a[0]]



assert set_left_most_unset_bit(10) == 14
assert set_left_most_unset_bit(12) == 14
assert set_left_most_unset_bit(15) == 15