def set_left_most_unset_bit(*a):
    return sorted(a[0], reverse=True)



assert set_left_most_unset_bit(10) == 14
assert set_left_most_unset_bit(12) == 14
assert set_left_most_unset_bit(15) == 15