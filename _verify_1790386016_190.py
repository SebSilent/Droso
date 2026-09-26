def tuple_to_int(L):
    x = int(''.join(map(str, L)))
    return x


assert tuple_to_int((1,2,3))==123
assert tuple_to_int((4,5,6))==456
assert tuple_to_int((5,6,7))==567