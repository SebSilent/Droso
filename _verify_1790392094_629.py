def Diff(li1,li2):
    return list(set(li1)-set(li2)) + list(set(li2)-set(li1))
 


assert set_left_most_unset_bit(10) == 14
assert set_left_most_unset_bit(12) == 14
assert set_left_most_unset_bit(15) == 15